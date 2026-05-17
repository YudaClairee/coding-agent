import asyncio
from typing import Any

from agno.agent import Agent, RunEvent

type StreamEvent = tuple[str, str]


def stream_agent(
    agent: Agent,
    user_input: str,
    loop: asyncio.AbstractEventLoop,
    queue: asyncio.Queue[StreamEvent | None],
    session_id: str | None = None,
) -> None:
    """Run agent streaming in a background thread, pushing events to queue."""

    def _send(tag: str, text: str) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, (tag, text))

    try:
        run: Any = agent.run(user_input, session_id=session_id, stream=True, stream_events=True)
        for chunk in run:
            event = getattr(chunk, "event", None)
            if event == RunEvent.tool_call_started:
                tool = getattr(chunk, "tool", None)
                name = getattr(tool, "tool_name", "tool") if tool else "tool"
                _send("tool_start", name or "tool")
            elif event == RunEvent.tool_call_completed:
                _send("tool_end", "")
            elif event == RunEvent.reasoning_content_delta:
                # Fires for step-based reasoning (reasoning tools).
                delta = getattr(chunk, "reasoning_content", "") or ""
                if delta:
                    _send("reasoning", delta)
            elif event == RunEvent.run_content:
                # Native model reasoning is piggybacked on run_content chunks
                # via a separate `reasoning_content` field, independent of
                # `content`. Emit each independently so tool-call rounds
                # (which often have empty content but populated reasoning)
                # aren't dropped.
                reasoning_delta = getattr(chunk, "reasoning_content", "") or ""
                if reasoning_delta:
                    _send("reasoning", reasoning_delta)
                if chunk.content:
                    _send("content", chunk.content)
    except Exception as e:
        _send("content", f"\n\nError: {e}")
    finally:
        loop.call_soon_threadsafe(queue.put_nowait, None)
