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

## How the dashboard cards are computed

On page load the frontend calls `GET /api/summary` (`summary()` in
`backend/main.py`). The numbers are computed live from the same data source
the chat tools use, so chat answers always agree with the header cards:

| Card | Computation |
|---|---|
| **Net worth** | Sum of all `ACCOUNTS` balances in `data.py`. The credit-card balance is stored negative, so debt is subtracted automatically. |
| **Spent this month** | Sum of negative-amount `TRANSACTIONS` whose date falls in the current month (negative = spending, positive = income). |
| **Bills due soon** | `_get_bills()` computes each bill's next due date from its `due_day`; bills due within the next 10 days count, and the soonest one is shown as "next". |

The underlying data is a fake bank in `data.py`: accounts, budgets, bills,
and the portfolio are hardcoded, while ~6 months of transactions are
generated with a fixed seed (`random.seed(42)`) — salary twice a month,
bills posting on their due days, and randomized merchant purchases with a
deliberate dining-out uptrend so spending analysis has a real pattern to
find. Swap `data.py` for a bank aggregator (e.g. Plaid) and the dashboard,
tools, and chat all work unchanged.

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

## Privacy & data safety

This repo ships with **synthetic data only** (`data.py`) — nothing real is at
risk while demoing. If you connect real financial data, know the trade-offs:

- **Everything the tools return is sent to the model provider.** Chat
  messages and tool results (balances, transactions) go to whichever LLM the
  backend uses. Choose accordingly:
  - *Free endpoints (Groq, etc.)* — weaker data commitments; use for
    development against fake data, not real finances.
  - *Anthropic API* — API inputs/outputs are not used for training by
    default; the standard choice for real data.
  - *Local (Ollama)* — data never leaves your machine; weaker tool calling.
- **Keep credentials away from the LLM.** With an aggregator like Plaid, bank
  logins go to the aggregator and your server holds an access token. The
  model should only ever see descriptions and amounts — strip account
  numbers and identifiers in the tool layer before results are returned.
- **Minimize what you send.** Prefer aggregates (`analyze_spending`) over raw
  transaction dumps where possible.
- **Tools are read-only by design** (the one write, `set_bill_reminder`, is
  an in-memory demo stub). Keep money-moving actions out of tool reach, or
  gate them behind explicit human confirmation — transaction text is
  external input and a prompt-injection surface.
- **Local use only, as shipped.** Conversations live in server memory (gone
  on restart) and nothing is persisted, but there is no auth or TLS — add
  both before deploying anywhere public.

## Notes

- Model: `claude-opus-4-8` with `thinking: {type: "adaptive"}` and a cached system prompt (`cache_control: ephemeral`).
- Streaming: token deltas, tool-activity, and thinking status are forwarded to the UI as SSE events.
- Demo data is generated with a fixed seed in `data.py`; replace it with a real aggregator for production.
- Educational guidance only — not licensed financial advice.
