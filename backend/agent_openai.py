"""OpenAI-compatible streaming agent — the free-model testing path.

Speaks the chat-completions wire format, so it works with any
OpenAI-compatible endpoint. Defaults target Groq's free tier.

    LLM_PROVIDER=openai
    LLM_API_KEY=gsk_...                              # Groq key (free at console.groq.com)
    LLM_BASE_URL=https://api.groq.com/openai/v1      # default
    LLM_MODEL=llama-3.3-70b-versatile                # default

This path exists to test the plumbing (tool loop, streaming, UI) without an
Anthropic key. It lacks Claude-specific features (adaptive thinking, prompt
caching) and free models are less reliable at multi-tool calls — judge answer
quality against agent.py, not this adapter.
"""

import json
import os
from typing import Generator

import openai
from dotenv import load_dotenv

from prompts import SYSTEM_PROMPT
from tools import TOOL_LABELS, TOOLS, execute_tool

load_dotenv()

BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
MAX_TOOL_ROUNDS = 8

# Anthropic tool schema -> OpenAI function-calling schema.
OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["input_schema"],
        },
    }
    for t in TOOLS
]

client = openai.OpenAI(
    base_url=BASE_URL,
    api_key=os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY") or "missing",
)


def stream_turn(messages: list) -> Generator[dict, None, None]:
    """Run one user turn to completion, mutating `messages` in place.
    History is kept in chat-completions format (role/content/tool_calls)."""
    try:
        for _ in range(MAX_TOOL_ROUNDS):
            stream = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}, *messages],
                tools=OPENAI_TOOLS,
                stream=True,
            )

            text_parts: list[str] = []
            calls: dict[int, dict] = {}
            finish = None
            for chunk in stream:
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                delta = choice.delta
                if delta and delta.content:
                    text_parts.append(delta.content)
                    yield {"type": "delta", "text": delta.content}
                if delta and delta.tool_calls:
                    for tc in delta.tool_calls:
                        entry = calls.setdefault(tc.index, {"id": "", "name": "", "args": ""})
                        if tc.id:
                            entry["id"] = tc.id
                        if tc.function and tc.function.name:
                            entry["name"] = tc.function.name
                            yield {"type": "tool", "name": entry["name"],
                                   "label": TOOL_LABELS.get(entry["name"], f"Running {entry['name']}")}
                        if tc.function and tc.function.arguments:
                            entry["args"] += tc.function.arguments
                if choice.finish_reason:
                    finish = choice.finish_reason

            if calls and finish == "tool_calls":
                ordered = [calls[i] for i in sorted(calls)]
                messages.append({
                    "role": "assistant",
                    "content": "".join(text_parts) or None,
                    "tool_calls": [
                        {"id": c["id"], "type": "function",
                         "function": {"name": c["name"], "arguments": c["args"] or "{}"}}
                        for c in ordered
                    ],
                })
                for c in ordered:
                    try:
                        args = json.loads(c["args"] or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    messages.append({
                        "role": "tool",
                        "tool_call_id": c["id"],
                        "content": execute_tool(c["name"], args),
                    })
                continue

            messages.append({"role": "assistant", "content": "".join(text_parts)})
            yield {"type": "done"}
            return

        yield {"type": "error", "message": "Reached the tool-use round limit for this turn."}
    except openai.AuthenticationError:
        yield {"type": "error",
               "message": "LLM_API_KEY missing or invalid. Get a free Groq key at console.groq.com and set it in backend/.env."}
    except openai.RateLimitError:
        yield {"type": "error", "message": "Rate limited by the free tier — wait a moment and try again."}
    except openai.APIStatusError as exc:
        yield {"type": "error", "message": f"API error ({exc.status_code}): {exc.message}"}
    except openai.APIConnectionError:
        yield {"type": "error", "message": f"Could not reach {BASE_URL}. Check your connection."}
