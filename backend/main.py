"""FastAPI backend for the personal finance copilot."""

import json
import os
import uuid
from collections import defaultdict
from datetime import date

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from data import ACCOUNTS, TRANSACTIONS
from tools import _get_bills

load_dotenv()

# Provider switch: "anthropic" (default, agent.py) or "openai" — any
# OpenAI-compatible endpoint, e.g. Groq's free tier (agent_openai.py).
if os.getenv("LLM_PROVIDER", "anthropic").lower() == "openai":
    from agent_openai import stream_turn
else:
    from agent import stream_turn

app = FastAPI(title="Personal Finance Copilot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Server-side conversation store. Sessions hold the full message history,
# including tool_use / tool_result blocks, so multi-turn context is preserved.
SESSIONS: dict[str, list] = {}


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


@app.post("/api/chat")
def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    messages = SESSIONS.setdefault(session_id, [])
    messages.append({"role": "user", "content": req.message})

    def sse():
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
        for event in stream_turn(messages):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/summary")
def summary():
    """Dashboard cards for the frontend header."""
    month = date.today().strftime("%Y-%m")
    spent = defaultdict(float)
    for t in TRANSACTIONS:
        if t["date"].startswith(month) and t["amount"] < 0:
            spent["total"] += -t["amount"]
    bills = _get_bills(days_ahead=10)
    due_soon = [b for b in bills["bills"] if b["due_soon"]]
    return {
        "net_worth": round(sum(a["balance"] for a in ACCOUNTS), 2),
        "spent_this_month": round(spent["total"], 2),
        "bills_due_soon": len(due_soon),
        "next_bill": due_soon[0] if due_soon else None,
        "accounts": ACCOUNTS,
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}
