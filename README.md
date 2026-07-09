# Personal Finance Copilot

A conversational personal-finance assistant: **FastAPI + Anthropic Claude** backend with tool use and SSE streaming, and an **Angular 20** chat frontend.

## Capabilities

- Explain financial statements and transactions in plain language
- Analyze spending patterns (per-category trends, top merchants)
- Budget recommendations grounded in actual spend vs. budget
- Savings suggestions with concrete dollar amounts
- Bill overview + reminders (`set_bill_reminder` tool)
- Investment education (index funds, diversification, DCA, …)
- Portfolio Q&A: holdings, gains/losses, asset allocation
- Personalized financial plans sequenced across goals and debt

## Architecture

```
frontend (Angular 20, :4200)
   │  POST /api/chat  ──►  SSE stream (deltas, tool events)
   ▼
backend (FastAPI, :8000)
   ├─ agent.py   — streaming agentic loop on claude-opus-4-8
   │              (adaptive thinking, prompt caching, manual tool loop)
   ├─ tools.py   — 8 finance tools (accounts, transactions, spending
   │              analysis, budgets, bills, reminders, portfolio, goals)
   ├─ data.py    — deterministic sample data (swap for Plaid/bank APIs)
   └─ main.py    — /api/chat (SSE), /api/summary, in-memory sessions
```

Conversation history (including tool_use/tool_result blocks) is kept server-side per `session_id`, so follow-up questions retain full context.

## Run it

### Backend

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env        # add your ANTHROPIC_API_KEY
.venv/bin/uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install                 # already done if scaffolded locally
npm start                   # serves on http://localhost:4200
```

Open http://localhost:4200 — the dashboard cards load from `/api/summary`; chat requires the API key.

## Testing without an Anthropic key (free models)

The backend has a second, OpenAI-compatible agent path for testing the
plumbing (tool loop, streaming, UI) on free endpoints. In `backend/.env`:

```bash
LLM_PROVIDER=openai
LLM_API_KEY=gsk_...                          # free key from console.groq.com
# LLM_BASE_URL=https://api.groq.com/openai/v1   (default)
# LLM_MODEL=llama-3.3-70b-versatile             (default)
```

Works with any OpenAI-compatible endpoint (Groq, Gemini's compatibility API,
Ollama at `http://localhost:11434/v1`, …). Caveat: free models are noticeably
less reliable at multi-tool calls, and this path lacks Claude's adaptive
thinking and prompt caching — judge answer quality on the Anthropic path.

## Notes

- Model: `claude-opus-4-8` with `thinking: {type: "adaptive"}` and a cached system prompt (`cache_control: ephemeral`).
- Streaming: token deltas, tool-activity, and thinking status are forwarded to the UI as SSE events.
- Demo data is generated with a fixed seed in `data.py`; replace it with a real aggregator for production.
- Educational guidance only — not licensed financial advice.
