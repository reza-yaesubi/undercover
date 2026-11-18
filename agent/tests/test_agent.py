import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import main
from backend.database import Database
from backend.main import create_app


@pytest.fixture
def api(tmp_path):
    return create_app(Database(tmp_path / "agent-test.sqlite3"))


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


def test_check_backend(monkeypatch, api):
    monkeypatch.setattr(main, "backend", lambda: TestClient(api))
    assert main.check_backend.invoke({}) == "ok"


def test_run(monkeypatch, api):
    monkeypatch.setattr(main, "backend", lambda: TestClient(api))
    replies = [
        AIMessage(
            content="", tool_calls=[{"name": "check_backend", "args": {}, "id": "1"}]
        ),
        AIMessage(content="Hello! The backend is up."),
    ]
    assert (
        main.run("CLM-1001", "thread-1", StubModel(messages=iter(replies)))
        == "Hello! The backend is up."
    )


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert main.model().model_name == "openai/gpt-6-luna"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"
