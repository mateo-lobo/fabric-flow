import os
from typing import Any

import openai
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

from .state import Session, store
from .tools import build_tools

SYSTEM_PROMPT = """You are the FabricFlow assistant for bag production. You help users work out fabric \
consumption, cutting efficiency and cost by collecting their inputs through conversation.

Rules:
- Reply in the user's language (Portuguese or English).
- Ask for at most two missing things at a time. Needed inputs: fabric rolls (width cm, length m, price R$/m, \
rotation allowed?, directional pattern?), pattern pieces (shape, size cm, quantity per bag, which roll), \
hardware (price, quantity per bag), model name and batch size.
- State units on every number: cm, m, R$.
- Save inputs with the tools as soon as the user gives them; never guess missing values.
- Before running run_calculation, briefly confirm the collected inputs with the user.
- Never do arithmetic yourself: every cost, efficiency or quantity you quote must come from a tool result.
- After a calculation, explain the result in plain language and, when useful, suggest what-if checks with \
compare_alternative or scrap reuse with apply_scrap_scenario (only apply after the user agrees).
- If a tool returns an error, turn it into a clear question or explanation for the user."""


class AgentUnavailable(RuntimeError):
    """Raised when no LLM is configured."""


class UpstreamError(RuntimeError):
    """Raised when the LLM provider rejects or fails a request; the message is user-safe."""


def explain_provider_error(error: openai.OpenAIError) -> str:
    if isinstance(error, openai.RateLimitError) and "insufficient_quota" in str(error):
        return "The OpenAI account has no credits left. Add credits in the OpenAI billing settings."
    if isinstance(error, openai.RateLimitError):
        return "The OpenAI rate limit was hit. Wait a moment and try again."
    if isinstance(error, openai.AuthenticationError):
        return "OpenAI rejected the API key. Check OPENAI_API_KEY in backend/.env."
    if isinstance(error, openai.APIConnectionError):
        return "Could not reach OpenAI. Check the internet connection."
    return f"The language model request failed ({type(error).__name__})."


def get_chat_model() -> BaseChatModel:
    if not os.environ.get("OPENAI_API_KEY"):
        raise AgentUnavailable("OPENAI_API_KEY is not set; the assistant is unavailable.")
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=os.environ.get("FABRICFLOW_LLM_MODEL", "gpt-4o-mini"), temperature=0)


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    return "".join(
        block.get("text", "") if isinstance(block, dict) else str(block) for block in content
    )


def run_chat(session_id: str, message: str, model: BaseChatModel | None = None) -> dict[str, Any]:
    session: Session = store.get(session_id)
    agent = create_agent(model or get_chat_model(), build_tools(session), system_prompt=SYSTEM_PROMPT)
    try:
        result = agent.invoke({"messages": [*session.messages, HumanMessage(message)]})
    except openai.OpenAIError as error:
        raise UpstreamError(explain_provider_error(error)) from error
    session.messages = result["messages"]
    return {
        "reply": _text(session.messages[-1].content),
        "draft": session.draft(),
        "result": session.last_result,
    }
