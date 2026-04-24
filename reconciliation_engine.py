# ==============================
# reconciliation_engine.py
# ==============================

from collections import defaultdict
from ledger.db import SessionLocal
from ledger.models import JournalEntry, Account


def _rebuild_from_ledger(session):

    balances = defaultdict(float)

    entries = session.query(JournalEntry).all()

    for e in entries:
        if e.entry_type == "CREDIT":
            balances[e.account_id] += e.amount
        elif e.entry_type == "DEBIT":
            balances[e.account_id] -= e.amount

    return balances


def run_reconciliation():

    session = SessionLocal()

    ledger_balances = _rebuild_from_ledger(session)
    accounts = session.query(Account).all()

    issues = []

    for acc in accounts:

        ledger_val = round(ledger_balances.get(acc.id, 0.0), 2)
        actual_val = round(acc.balance, 2)

        if abs(ledger_val - actual_val) > 0.01:
            issues.append({
                "account": acc.id,
                "ledger": ledger_val,
                "actual": actual_val,
                "diff": round(actual_val - ledger_val, 2)
            })

    session.close()

    return issues


# backward compatibility
def run_full_reconciliation():
    return run_reconciliation()