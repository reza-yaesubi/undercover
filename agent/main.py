"""The UnderCover Agent."""

import os
from contextlib import closing
from dataclasses import dataclass
from urllib.parse import quote

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool, tool
from langchain_openai import ChatOpenAI
from pydantic import JsonValue, SecretStr

from backend.models import Instructions
from backend.workflow_models import DecisionDraft

load_dotenv(override=True)

BACKEND_URL = "http://localhost:8000"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=10)


def request(
    method: str, path: str, body: dict[str, JsonValue] | None = None
) -> httpx.Response:
    with closing(backend()) as client:
        response = client.request(method, path, json=body)
    response.raise_for_status()
    return response


@dataclass(frozen=True)
class ClaimAPI:
    claim_id: str
    thread_id: str

    @property
    def path(self) -> str:
        return f"/api/claims/{quote(self.claim_id, safe='')}"

    def event(self, kind: str, message: str) -> None:
        request(
            "POST",
            f"{self.path}/activity",
            {"thread_id": self.thread_id, "kind": kind, "message": message},
        )

    def call(
        self,
        method: str,
        path: str,
        message: str,
        body: dict[str, JsonValue] | None = None,
    ) -> str:
        self.event("tool_call", message)
        response = request(method, path, body)
        self.event("tool_result", f"{message} Completed.")
        return response.text


def tools_for(api: ClaimAPI) -> list[BaseTool]:
    @tool
    def read_claim() -> str:
        """Read this claim's evidence, policy, plan, add-ons and customer history."""
        return api.call("GET", api.path, "Read claim, policy and customer history.")

    @tool
    def read_policy_wording() -> str:
        """Read the full policy wording governing this claim."""
        return api.call("GET", "/api/policy-wording", "Read policy wording.")

    @tool
    def record_decision(decision: DecisionDraft) -> str:
        """Store a decision with its payout, reasons, calculation and sections."""
        return api.call(
            "POST",
            f"{api.path}/decision",
            f"Record {decision.outcome} decision.",
            {**decision.model_dump(mode="json"), "thread_id": api.thread_id},
        )

    @tool
    def pay_claim(amount: str) -> str:
        """Request exactly the approved USD amount as a guarded simulated payment."""
        return api.call(
            "POST",
            f"{api.path}/pay",
            "Request a simulated payment.",
            {"amount": amount},
        )

    return [read_claim, read_policy_wording, record_decision, pay_claim]


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or GPT-6 Luna by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
    )


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Run the agent on one claim and return its final reply."""
    api = ClaimAPI(claim_id, thread_id)
    instructions = Instructions.model_validate_json(
        api.call("GET", "/api/agent/instructions", "Read agent instructions.")
    )
    agent = create_agent(
        llm or model(), tools=tools_for(api), system_prompt=instructions.content
    )
    result = agent.invoke(
        {"messages": [{"role": "user", "content": f"Claim {claim_id}"}]},
        config={"configurable": {"thread_id": thread_id}, "recursion_limit": 30},
    )
    return result["messages"][-1].text
