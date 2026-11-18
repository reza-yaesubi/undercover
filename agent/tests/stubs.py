"""Scripted chat models that still execute the actual agent tools."""

import time
from collections.abc import Iterator

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatResult
from pydantic import Field, JsonValue

from backend.tests.pilot_data import draft_for


class StubModel(GenericFakeChatModel):
    seen_messages: list[list[BaseMessage]] = Field(default_factory=list)

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs,
    ) -> ChatResult:
        self.seen_messages.append(list(messages))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def tool_message(name: str, args: dict[str, JsonValue]) -> AIMessage:
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args, "id": f"call-{name}"}]
    )


def scripted_model(claim_id: str, delay: float = 0) -> StubModel:
    decision = draft_for(claim_id)

    def replies() -> Iterator[AIMessage]:
        yield tool_message("read_claim", {})
        yield tool_message("read_policy_wording", {})
        if delay:
            time.sleep(delay)
        yield tool_message(
            "record_decision", {"decision": decision.model_dump(mode="json")}
        )
        if decision.outcome == "approve" and 0 < decision.payout <= 1000:
            yield tool_message("pay_claim", {"amount": f"{decision.payout:.2f}"})
        yield AIMessage(content="The claim decision has been recorded.")

    return StubModel(messages=iter(replies()))
