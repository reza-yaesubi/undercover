from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

from agent import main
from agent.tests.stubs import StubModel, scripted_model, tool_message
from backend.database import Database
from backend.main import create_app
from backend.seed import DATA_DIR
from backend.tests.pilot_data import SCENARIOS, draft_for, pilot_seed
from backend.workflow import begin_run


@pytest.fixture
def api(tmp_path, monkeypatch):
    database = Database(tmp_path / "agent-test.sqlite3")
    app = create_app(database, pilot_seed())
    with TestClient(app) as client:

        def forward(request: httpx.Request) -> httpx.Response:
            response = client.request(
                request.method,
                request.url.path,
                content=request.content,
                headers=dict(request.headers),
            )
            return httpx.Response(
                response.status_code,
                content=response.content,
                headers=dict(response.headers),
            )

        monkeypatch.setattr(
            main,
            "backend",
            lambda: httpx.Client(
                base_url="http://testserver", transport=httpx.MockTransport(forward)
            ),
        )
        yield client, database


@pytest.mark.parametrize("claim_id", list(SCENARIOS))
def test_agent_tools_use_api_context_and_persist_decisions(api, claim_id, monkeypatch):
    client, database = api
    started = begin_run(database, claim_id)
    llm = scripted_model(claim_id)
    read_text = Path.read_text

    def forbid_business_files(path, *args, **kwargs):
        assert DATA_DIR not in path.parents
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", forbid_business_files)
    assert "recorded" in main.run(claim_id, started.thread_id, llm)
    detail = client.get(f"/api/claims/{claim_id}").json()
    decision = draft_for(claim_id)
    assert detail["decision"]["outcome"] == decision.outcome
    assert detail["decision"]["payout"] == f"{decision.payout:.2f}"
    assert detail["decision"]["policy_sections"] == decision.policy_sections
    messages = llm.seen_messages[-1]
    assert isinstance(messages[0], SystemMessage)
    assert (
        messages[0].content == client.get("/api/agent/instructions").json()["content"]
    )
    tool_text = "\n".join(
        message.text for message in messages if isinstance(message, ToolMessage)
    )
    for key in ["previous_claims", "documents", "policy", "plan", "policy_id"]:
        assert key in tool_text
    assert "## 10. How we work out your payment" in tool_text
    if decision.outcome == "approve" and 0 < decision.payout <= 1000:
        assert detail["payment"]["simulated"]
    else:
        assert detail["payment"] is None


def test_over_limit_agent_cannot_pay_or_sign_off(api):
    client, database = api
    claim_id = "CLM-T100001"
    started = begin_run(database, claim_id)
    llm = StubModel(
        messages=iter(
            [
                tool_message(
                    "record_decision",
                    {"decision": draft_for(claim_id).model_dump(mode="json")},
                ),
                tool_message("pay_claim", {"amount": "1000.01"}),
            ]
        )
    )
    with pytest.raises(httpx.HTTPStatusError) as error:
        main.run(claim_id, started.thread_id, llm)
    assert error.value.response.status_code == 409
    assert error.value.response.json() == {"detail": "Handler sign-off required"}
    assert client.get(f"/api/claims/{claim_id}").json()["payment"] is None
    tools = main.tools_for(main.ClaimAPI(claim_id, started.thread_id))
    assert {tool.name for tool in tools} == {
        "read_claim",
        "read_policy_wording",
        "record_decision",
        "pay_claim",
    }
    for tool in tools:
        assert "claim_id" not in tool.args
        assert "thread_id" not in tool.args


def test_instruction_api_failure_does_not_fall_back(api, monkeypatch):
    _client, database = api
    started = begin_run(database, "CLM-T420")
    paths = []

    def respond(request):
        paths.append(request.url.path)
        if request.url.path.endswith("/activity"):
            return httpx.Response(201, json={"sequence": 1})
        return httpx.Response(503, text="Unavailable")

    monkeypatch.setattr(
        main,
        "backend",
        lambda: httpx.Client(
            base_url="http://test", transport=httpx.MockTransport(respond)
        ),
    )
    with pytest.raises(httpx.HTTPStatusError):
        main.run(
            "CLM-T420",
            started.thread_id,
            StubModel(messages=iter([AIMessage(content="unused")])),
        )
    assert paths == ["/api/claims/CLM-T420/activity", "/api/agent/instructions"]


def test_model_configuration_and_default_backend(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    llm = main.model()
    assert llm.model_name == "openai/gpt-6-luna"
    assert llm.reasoning_effort == "low"
    assert llm.openai_api_base == "https://openrouter.ai/api/v1"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    override = main.model()
    assert override.model_name == "openrouter/free"
    assert override.reasoning_effort is None
    with main.backend() as client:
        assert str(client.base_url) == "http://localhost:8000"
