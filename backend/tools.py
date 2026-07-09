"""Tool definitions and executors for the finance copilot.

Each tool returns a JSON string. Claude decides which tools to call based on
the user's question; the agent loop in agent.py executes them and feeds the
results back.
"""

import json
from collections import defaultdict
from datetime import date, timedelta

from data import ACCOUNTS, BILLS, BUDGETS, GOALS, PORTFOLIO, TRANSACTIONS, USER_PROFILE

TOOLS = [
    {
        "name": "get_accounts",
        "description": "Get all of the user's financial accounts with current balances: checking, savings, credit cards, brokerage, and retirement. Call this for net-worth, balance, or account questions.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_transactions",
        "description": "Get the user's individual transactions. Call this when the user asks about specific purchases, a merchant, or wants their statement explained. Amounts are negative for spending, positive for income.",
        "input_schema": {
            "type": "object",
            "properties": {
                "month": {"type": "string", "description": "Filter to one month, format YYYY-MM. Omit for the most recent transactions."},
                "category": {"type": "string", "description": "Filter to one spending category, e.g. 'Dining Out', 'Groceries'."},
                "limit": {"type": "integer", "description": "Max transactions to return. Default 50."},
            },
            "required": [],
        },
    },
    {
        "name": "analyze_spending",
        "description": "Get aggregated spending by category per month, with month-over-month trends and top merchants. Call this for spending-pattern analysis, 'where does my money go', or budget-recommendation questions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "months": {"type": "integer", "description": "How many recent months to analyze (1-6). Default 3."},
            },
            "required": [],
        },
    },
    {
        "name": "get_budgets",
        "description": "Get the user's monthly budget per category alongside actual spending for the current month, including over/under status.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_bills",
        "description": "Get the user's recurring bills with amounts, due dates, autopay status, and which ones are due soon. Call this for bill-reminder or cash-flow questions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {"type": "integer", "description": "Look-ahead window in days for 'due soon'. Default 14."},
            },
            "required": [],
        },
    },
    {
        "name": "set_bill_reminder",
        "description": "Set a reminder for a specific bill a given number of days before it is due. Use when the user asks to be reminded about a bill.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bill_name": {"type": "string", "description": "Name of the bill, matching a bill from get_bills."},
                "days_before": {"type": "integer", "description": "How many days before the due date to remind. Default 3."},
            },
            "required": ["bill_name"],
        },
    },
    {
        "name": "get_portfolio",
        "description": "Get the user's investment portfolio: holdings, cost basis, market value, gains/losses, and asset allocation. Call this for portfolio, investment-performance, or allocation questions.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_financial_goals",
        "description": "Get the user's savings goals with targets, progress, and deadlines. Also returns income and risk profile. Call this for savings suggestions and personalized financial planning.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]

# Human-friendly labels shown in the UI while a tool runs.
TOOL_LABELS = {
    "get_accounts": "Looking up your accounts",
    "get_transactions": "Pulling your transactions",
    "analyze_spending": "Analyzing your spending patterns",
    "get_budgets": "Checking your budgets",
    "get_bills": "Reviewing your bills",
    "set_bill_reminder": "Setting your reminder",
    "get_portfolio": "Fetching your portfolio",
    "get_financial_goals": "Loading your goals",
}

# Reminders created during the session (in-memory for the demo).
REMINDERS: list[dict] = []


def _current_month() -> str:
    return date.today().strftime("%Y-%m")


def _get_transactions(month=None, category=None, limit=50):
    txns = TRANSACTIONS
    if month:
        txns = [t for t in txns if t["date"].startswith(month)]
    if category:
        txns = [t for t in txns if t["category"].lower() == category.lower()]
    return {"count": len(txns[:limit]), "transactions": txns[:limit]}


def _analyze_spending(months=3):
    months = max(1, min(int(months or 3), 6))
    by_month = defaultdict(lambda: defaultdict(float))
    merchants = defaultdict(float)
    for t in TRANSACTIONS:
        if t["amount"] >= 0:
            continue
        by_month[t["date"][:7]][t["category"]] += -t["amount"]
        merchants[t["merchant"]] += -t["amount"]
    recent = sorted(by_month.keys(), reverse=True)[:months]
    breakdown = {
        m: {cat: round(v, 2) for cat, v in sorted(by_month[m].items(), key=lambda kv: -kv[1])}
        for m in sorted(recent)
    }
    totals = {m: round(sum(by_month[m].values()), 2) for m in sorted(recent)}
    top_merchants = sorted(merchants.items(), key=lambda kv: -kv[1])[:8]
    return {
        "months_analyzed": sorted(recent),
        "total_spend_per_month": totals,
        "spend_by_category_per_month": breakdown,
        "top_merchants_all_time": [{"merchant": m, "total": round(v, 2)} for m, v in top_merchants],
        "monthly_take_home_income": USER_PROFILE["monthly_take_home_income"],
    }


def _get_budgets():
    month = _current_month()
    actual = defaultdict(float)
    for t in TRANSACTIONS:
        if t["date"].startswith(month) and t["amount"] < 0:
            actual[t["category"]] += -t["amount"]
    rows = []
    for cat, budget in BUDGETS.items():
        spent = round(actual.get(cat, 0.0), 2)
        rows.append({
            "category": cat,
            "budget": budget,
            "spent_this_month": spent,
            "remaining": round(budget - spent, 2),
            "status": "over" if spent > budget else "on_track",
        })
    return {"month": month, "budgets": rows}


def _get_bills(days_ahead=14):
    days_ahead = int(days_ahead or 14)
    today = date.today()
    bills = []
    for b in BILLS:
        due = today.replace(day=min(b["due_day"], 28))
        if due < today:
            next_month = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
            due = next_month.replace(day=min(b["due_day"], 28))
        days_until = (due - today).days
        bills.append({**b, "next_due_date": str(due), "days_until_due": days_until,
                      "due_soon": days_until <= days_ahead})
    bills.sort(key=lambda b: b["days_until_due"])
    return {"today": str(today), "bills": bills,
            "total_monthly_bills": round(sum(b["amount"] for b in BILLS), 2),
            "active_reminders": REMINDERS}


def _set_bill_reminder(bill_name, days_before=3):
    match = next((b for b in BILLS if b["name"].lower() == bill_name.lower()), None)
    if not match:
        return {"ok": False, "error": f"No bill named '{bill_name}'. Available: {[b['name'] for b in BILLS]}"}
    reminder = {"bill_name": match["name"], "days_before": int(days_before or 3),
                "amount": match["amount"], "due_day": match["due_day"]}
    REMINDERS.append(reminder)
    return {"ok": True, "reminder": reminder}


def _get_portfolio():
    holdings = []
    for h in PORTFOLIO["holdings"]:
        gain = round(h["market_value"] - h["cost_basis"], 2)
        holdings.append({**h, "gain_loss": gain,
                         "gain_loss_pct": round(gain / h["cost_basis"] * 100, 2)})
    alloc = defaultdict(float)
    for h in holdings:
        alloc[h["asset_class"]] += h["market_value"]
    total = PORTFOLIO["total_value"]
    return {
        "as_of": PORTFOLIO["as_of"],
        "total_value": total,
        "total_cost_basis": PORTFOLIO["total_cost_basis"],
        "total_gain_loss": round(total - PORTFOLIO["total_cost_basis"], 2),
        "holdings": holdings,
        "allocation_pct": {k: round(v / total * 100, 1) for k, v in alloc.items()},
        "risk_tolerance": USER_PROFILE["risk_tolerance"],
    }


def _get_goals():
    goals = [{**g, "progress_pct": round(g["saved"] / g["target"] * 100, 1)} for g in GOALS]
    return {"profile": USER_PROFILE, "goals": goals}


def execute_tool(name: str, tool_input: dict) -> str:
    try:
        if name == "get_accounts":
            result = {"accounts": ACCOUNTS,
                      "net_worth": round(sum(a["balance"] for a in ACCOUNTS), 2)}
        elif name == "get_transactions":
            result = _get_transactions(**tool_input)
        elif name == "analyze_spending":
            result = _analyze_spending(**tool_input)
        elif name == "get_budgets":
            result = _get_budgets()
        elif name == "get_bills":
            result = _get_bills(**tool_input)
        elif name == "set_bill_reminder":
            result = _set_bill_reminder(**tool_input)
        elif name == "get_portfolio":
            result = _get_portfolio()
        elif name == "get_financial_goals":
            result = _get_goals()
        else:
            return json.dumps({"error": f"Unknown tool: {name}"})
        return json.dumps(result)
    except Exception as exc:  # surface tool failures to the model, not the user
        return json.dumps({"error": str(exc)})
