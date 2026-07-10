"""Streaming agentic loop: Claude + finance tools.

Runs the manual tool-use loop with client.messages.stream so text reaches the
UI token-by-token, and yields UI events as dicts:
    {"type": "delta", "text": ...}     incremental assistant text
    {"type": "tool", "name", "label"}  a tool is being executed
    {"type": "thinking"}               model is reasoning before answering
    {"type": "done"}                   turn finished
    {"type": "error", "message": ...}  something went wrong
"""

import os
from typing import Generator

import anthropic
from dotenv import load_dotenv

from obs import agent_turn, llm_call, record_llm_usage, tool_call
from prompts import SYSTEM_PROMPT
from tools import TOOL_LABELS, TOOLS, execute_tool

load_dotenv()

MODEL = "claude-opus-4-8"
MAX_TOOL_ROUNDS = 8

client = anthropic.Anthropic()


def stream_turn(messages: list) -> Generator[dict, None, None]:
    """Run one user turn to completion, mutating `messages` in place so the
    caller's session history keeps the full tool-use trace."""
    try:
      with agent_turn("chat", history_len=len(messages)):
        for _ in range(MAX_TOOL_ROUNDS):
            with llm_call(MODEL) as llm_span, client.messages.stream(
                model=MODEL,
                max_tokens=64000,
                system=[{
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }],
                tools=TOOLS,
                thinking={"type": "adaptive"},
                messages=messages,
            ) as stream:
                for event in stream:
                    if event.type == "content_block_start":
                        if event.content_block.type == "thinking":
                            yield {"type": "thinking"}
                        elif event.content_block.type == "tool_use":
                            name = event.content_block.name
                            yield {"type": "tool", "name": name,
                                   "label": TOOL_LABELS.get(name, f"Running {name}")}
                    elif (event.type == "content_block_delta"
                          and event.delta.type == "text_delta"):
                        yield {"type": "delta", "text": event.delta.text}
                response = stream.get_final_message()
                if llm_span is not None:
                    usage = response.usage
                    record_llm_usage(
                        llm_span, MODEL,
                        input_tokens=usage.input_tokens,
                        output_tokens=usage.output_tokens,
                        cache_read_tokens=usage.cache_read_input_tokens or 0,
                        cache_write_tokens=usage.cache_creation_input_tokens or 0,
                    )

            # Preserve the full content blocks (thinking + tool_use) in history.
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "pause_turn":
                continue

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        with tool_call(block.name):
                            result = execute_tool(block.name, block.input or {})
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })
                messages.append({"role": "user", "content": tool_results})
                continue

            yield {"type": "done"}
            return

        yield {"type": "error", "message": "Reached the tool-use round limit for this turn."}
    except anthropic.AuthenticationError:
        yield {"type": "error",
               "message": "Anthropic API key missing or invalid. Set ANTHROPIC_API_KEY in backend/.env."}
    except anthropic.RateLimitError:
        yield {"type": "error", "message": "Rate limited — please wait a moment and try again."}
    except anthropic.APIStatusError as exc:
        yield {"type": "error", "message": f"API error ({exc.status_code}): {exc.message}"}
    except anthropic.APIConnectionError:
        yield {"type": "error", "message": "Could not reach the Anthropic API. Check your connection."}
