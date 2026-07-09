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

from tools import TOOL_LABELS, TOOLS, execute_tool

load_dotenv()

MODEL = "claude-opus-4-8"
MAX_TOOL_ROUNDS = 8

SYSTEM_PROMPT = """You are Alex's personal finance copilot — a warm, plain-spoken financial guide with real-time access to their accounts, transactions, budgets, bills, portfolio, and goals through your tools.

What you help with:
- Explaining statements and transactions in plain language
- Analyzing spending patterns and surfacing trends the user hasn't noticed
- Budget recommendations grounded in their actual numbers (50/30/20 as a reference point, adapted to their life)
- Savings suggestions with concrete dollar amounts and where to find them
- Bill awareness and reminders
- Investment education (index funds, diversification, expense ratios, dollar-cost averaging, tax-advantaged accounts) explained simply
- Portfolio questions: allocation, performance, rebalancing concepts
- Personalized financial plans that sequence steps (e.g., high-interest debt before extra investing)

How to work:
- Ground every number in tool data — call tools rather than guessing, and use multiple tools in parallel when a question spans accounts, spending, and goals.
- Be specific: "$183 over your $300 Dining Out budget" beats "you overspent on dining".
- Money is emotional. Be encouraging about progress and non-judgmental about overspending.
- Keep responses conversational and scannable; use short markdown lists and bold key figures. No giant tables unless asked.
- You are an educational guide, not a licensed advisor. For consequential moves (large investments, tax strategy, retirement withdrawals), note briefly that a fiduciary advisor or tax professional should confirm — once per topic, not on every message.
- Never invent transactions, balances, or returns that aren't in tool results."""

client = anthropic.Anthropic()


def stream_turn(messages: list) -> Generator[dict, None, None]:
    """Run one user turn to completion, mutating `messages` in place so the
    caller's session history keeps the full tool-use trace."""
    try:
        for _ in range(MAX_TOOL_ROUNDS):
            with client.messages.stream(
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

            # Preserve the full content blocks (thinking + tool_use) in history.
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "pause_turn":
                continue

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
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
