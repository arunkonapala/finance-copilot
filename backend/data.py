"""Sample financial data for the demo user.

In a real deployment this module would be replaced by calls to a banking
aggregator (Plaid, Yodlee) or the institution's own APIs. Data is generated
deterministically so the demo is reproducible across restarts.
"""

import random
from datetime import date, timedelta

random.seed(42)

USER_PROFILE = {
    "name": "Alex",
    "currency": "USD",
    "monthly_take_home_income": 6800.00,
    "risk_tolerance": "moderate",
}

ACCOUNTS = [
    {"id": "chk-1", "name": "Everyday Checking", "type": "checking", "balance": 4325.18},
    {"id": "sav-1", "name": "High-Yield Savings", "type": "savings", "balance": 12750.00, "apy": 4.10},
    {"id": "cc-1", "name": "Rewards Credit Card", "type": "credit_card", "balance": -1832.44, "apr": 24.99, "credit_limit": 8000},
    {"id": "inv-1", "name": "Brokerage Account", "type": "investment", "balance": 28460.90},
    {"id": "ret-1", "name": "401(k)", "type": "retirement", "balance": 46120.55},
]

BUDGETS = {
    "Housing": 1800,
    "Groceries": 550,
    "Dining Out": 300,
    "Transportation": 250,
    "Utilities": 220,
    "Subscriptions": 80,
    "Shopping": 250,
    "Health & Fitness": 120,
    "Entertainment": 150,
    "Travel": 200,
}

BILLS = [
    {"name": "Rent", "amount": 1800.00, "due_day": 1, "autopay": True, "category": "Housing"},
    {"name": "Electricity", "amount": 96.40, "due_day": 7, "autopay": False, "category": "Utilities"},
    {"name": "Internet", "amount": 79.99, "due_day": 12, "autopay": True, "category": "Utilities"},
    {"name": "Car Insurance", "amount": 142.50, "due_day": 15, "autopay": False, "category": "Transportation"},
    {"name": "Phone", "amount": 65.00, "due_day": 18, "autopay": True, "category": "Utilities"},
    {"name": "Gym Membership", "amount": 45.00, "due_day": 20, "autopay": True, "category": "Health & Fitness"},
    {"name": "Streaming Bundle", "amount": 32.97, "due_day": 24, "autopay": True, "category": "Subscriptions"},
    {"name": "Credit Card Payment", "amount": 450.00, "due_day": 27, "autopay": False, "category": "Debt"},
]

PORTFOLIO = {
    "as_of": str(date.today()),
    "total_value": 28460.90,
    "total_cost_basis": 24100.00,
    "holdings": [
        {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF", "shares": 52, "cost_basis": 11020.00, "market_value": 13899.60, "asset_class": "US Equity"},
        {"symbol": "VXUS", "name": "Vanguard Total International ETF", "shares": 78, "cost_basis": 4590.00, "market_value": 4867.20, "asset_class": "International Equity"},
        {"symbol": "BND", "name": "Vanguard Total Bond Market ETF", "shares": 45, "cost_basis": 3420.00, "market_value": 3307.50, "asset_class": "Bonds"},
        {"symbol": "AAPL", "name": "Apple Inc.", "shares": 15, "cost_basis": 2470.00, "market_value": 3450.00, "asset_class": "US Equity"},
        {"symbol": "NVDA", "name": "NVIDIA Corp.", "shares": 8, "cost_basis": 1400.00, "market_value": 1936.60, "asset_class": "US Equity"},
        {"symbol": "Cash", "name": "Money Market Sweep", "shares": None, "cost_basis": 1200.00, "market_value": 1000.00, "asset_class": "Cash"},
    ],
}

GOALS = [
    {"name": "Emergency Fund", "target": 20400.00, "saved": 12750.00, "deadline": "2026-12-31", "note": "3 months of expenses target"},
    {"name": "Japan Trip", "target": 4500.00, "saved": 1900.00, "deadline": "2027-04-01", "note": None},
    {"name": "Pay Off Credit Card", "target": 1832.44, "saved": 0.00, "deadline": "2026-10-31", "note": "Balance at 24.99% APR"},
]

_MERCHANTS = {
    "Groceries": [("Whole Foods", 60, 140), ("Trader Joe's", 35, 90), ("Safeway", 25, 80)],
    "Dining Out": [("Chipotle", 12, 18), ("Local Thai", 28, 55), ("Blue Bottle Coffee", 6, 14), ("DoorDash", 22, 48)],
    "Transportation": [("Shell Gas", 38, 62), ("Uber", 12, 34), ("BART Clipper", 20, 45)],
    "Shopping": [("Amazon", 15, 120), ("Target", 20, 85), ("Uniqlo", 30, 90)],
    "Entertainment": [("AMC Theatres", 16, 40), ("Steam", 10, 60), ("Ticketmaster", 45, 120)],
    "Health & Fitness": [("CVS Pharmacy", 10, 45), ("ClassPass", 25, 25)],
    "Travel": [("United Airlines", 150, 420), ("Airbnb", 120, 380)],
}

# Roughly how many discretionary purchases land in each category per month.
_FREQUENCY = {
    "Groceries": 6, "Dining Out": 9, "Transportation": 5, "Shopping": 4,
    "Entertainment": 2, "Health & Fitness": 2, "Travel": 0,
}


def _generate_transactions(months_back: int = 6) -> list[dict]:
    txns = []
    today = date.today()
    for m in range(months_back, -1, -1):
        anchor = (today.replace(day=15) - timedelta(days=30 * m))
        ym = anchor.strftime("%Y-%m")
        # Fixed bills post every month on their due day.
        for bill in BILLS:
            txns.append({
                "date": f"{ym}-{bill['due_day']:02d}",
                "merchant": bill["name"],
                "category": bill["category"],
                "amount": -bill["amount"],
                "account_id": "chk-1",
            })
        # Salary twice a month.
        for payday in (1, 15):
            txns.append({
                "date": f"{ym}-{payday:02d}",
                "merchant": "Employer Payroll",
                "category": "Income",
                "amount": USER_PROFILE["monthly_take_home_income"] / 2,
                "account_id": "chk-1",
            })
        # Discretionary spending with mild month-to-month drift so there are
        # real patterns to find (dining out creeps up in recent months).
        for category, freq in _FREQUENCY.items():
            count = freq + random.randint(-1, 2)
            if category == "Dining Out":
                count += max(0, 3 - m)  # recent months trend higher
            for _ in range(max(count, 0)):
                merchant, lo, hi = random.choice(_MERCHANTS[category])
                txns.append({
                    "date": f"{ym}-{random.randint(1, 28):02d}",
                    "merchant": merchant,
                    "category": category,
                    "amount": -round(random.uniform(lo, hi), 2),
                    "account_id": random.choice(["chk-1", "cc-1"]),
                })
        # One travel purchase every third month.
        if m % 3 == 0:
            merchant, lo, hi = random.choice(_MERCHANTS["Travel"])
            txns.append({
                "date": f"{ym}-{random.randint(1, 28):02d}",
                "merchant": merchant,
                "category": "Travel",
                "amount": -round(random.uniform(lo, hi), 2),
                "account_id": "cc-1",
            })
    txns.sort(key=lambda t: t["date"], reverse=True)
    return txns


TRANSACTIONS = _generate_transactions()
