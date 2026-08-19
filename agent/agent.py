"""Single-agent runtime, kept independent from the Streamlit UI."""
from __future__ import annotations
import asyncio
from collections.abc import Callable
from agents import Agent, Runner, set_default_openai_key
from agent.prompts import SYSTEM_PROMPT
from agent.tools import calculate, get_current_utc_time

class AgentConfigurationError(Exception): pass

def _input_history(history: list[dict[str, str]]) -> list[dict[str, str]]:
    return [{"role": item["role"], "content": item["content"]} for item in history if item["role"] in {"user", "assistant"}]

async def _stream(api_key: str, model: str, history: list[dict[str, str]], on_delta: Callable[[str], None], on_activity: Callable[[str], None], on_tool_call: Callable[[str, str], None] | None) -> str:
    if not api_key: raise AgentConfigurationError("This app is not configured yet. Add OPENAI_API_KEY to server secrets.")
    set_default_openai_key(api_key, use_for_tracing=False)
    agent = Agent(name="Assistant", instructions=SYSTEM_PROMPT, model=model, tools=[calculate, get_current_utc_time])
    # Four turns prevents accidental model/tool loops from consuming unbounded API usage.
    result = Runner.run_streamed(agent, input=_input_history(history[-30:]), max_turns=4)
    async for event in result.stream_events():
        if event.type == "raw_response_event" and getattr(event.data, "type", "") == "response.output_text.delta": on_delta(event.data.delta)
        elif event.type == "run_item_stream_event" and getattr(event.item, "type", "") == "tool_call_item":
            on_activity("Using a local tool…")
            raw_item = getattr(event.item, "raw_item", None)
            if on_tool_call:
                on_tool_call(str(getattr(raw_item, "name", "local_tool")), str(getattr(raw_item, "arguments", "{}")))
    return str(result.final_output or "I couldn't produce a response.")

def run_agent_stream(api_key: str, model: str, history: list[dict[str, str]], on_delta: Callable[[str], None], on_activity: Callable[[str], None], on_tool_call: Callable[[str, str], None] | None = None) -> str:
    return asyncio.run(_stream(api_key, model, history, on_delta, on_activity, on_tool_call))
