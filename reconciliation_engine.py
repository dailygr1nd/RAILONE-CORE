from collections import defaultdict
from ledger.db import SessionLocal
from ledger.models import JournalEntry, Account, Transaction


# --------------------------------
# 1. LEDGER INTEGRITY CHECK
# --------------------------------
def check_double_entry_integrity():
    session = SessionLocal()
    issues = []

    tx_groups = defaultdict(list)
    entries = session.query(JournalEntry).all()

    # group by tx_id
    for entry in entries:
        tx_groups[entry.tx_id].append(entry)

    # validate each transaction
    for tx_id, group in tx_groups.items():
        total_debit = 0.0
        total_credit = 0.0

        for e in group:
            if e.entry_type == "DEBIT":
                total_debit += e.amount
            elif e.entry_type == "CREDIT":
                total_credit += e.amount

        if round(total_debit, 2) != round(total_credit, 2):
            issues.append({
                "tx_id": tx_id,
                "problem": "DEBIT_CREDIT_MISMATCH",
                "debit": total_debit,
                "credit": total_credit
            })

    session.close()
    return issues


# --------------------------------
# 2. REBUILD BALANCES FROM LEDGER
# --------------------------------
def reconstruct_balances():
    session = SessionLocal()

    balances = defaultdict(float)
    entries = session.query(JournalEntry).all()

    for e in entries:
        if e.entry_type == "CREDIT":
            balances[e.account_id] += e.amount
        elif e.entry_type == "DEBIT":
            balances[e.account_id] -= e.amount

    session.close()
    return balances


# --------------------------------
# 3. COMPARE WITH ACTUAL BALANCES
# --------------------------------
def detect_balance_drift():
    session = SessionLocal()

    reconstructed = reconstruct_balances()
    db_accounts = session.query(Account).all()

    drift_report = []

    for acc in db_accounts:
        ledger_balance = round(reconstructed.get(acc.id, 0.0), 2)
        actual_balance = round(acc.balance, 2)

        if ledger_balance != actual_balance:
            drift_report.append({
                "account_id": acc.id,
                "ledger_balance": ledger_balance,
                "actual_balance": actual_balance,
                "difference": round(actual_balance - ledger_balance, 2)
            })

    session.close()
    return drift_report


# --------------------------------
# 4. DUPLICATE TX CHECK
# --------------------------------
def detect_duplicate_transactions():
    session = SessionLocal()

    tx_ids = defaultdict(int)
    txs = session.query(Transaction).all()

    for tx in txs:
        tx_ids[tx.id] += 1

    duplicates = [tx_id for tx_id, count in tx_ids.items() if count > 1]

    session.close()
    return duplicates


# --------------------------------
# MASTER AUDIT FUNCTION
# --------------------------------
def run_full_reconciliation():
    print("\n🔍 RUNNING FULL RECONCILIATION...\n")

    integrity_issues = check_double_entry_integrity()
    drift_issues = detect_balance_drift()
    duplicates = detect_duplicate_transactions()

    print("=== LEDGER INTEGRITY ===")
    if not integrity_issues:
        print("✔ All transactions balanced")
    else:
        for issue in integrity_issues:
            print(issue)

    print("\n=== BALANCE DRIFT ===")
    if not drift_issues:
        print("✔ No balance drift detected")
    else:
        for drift in drift_issues:
            print(drift)

    print("\n=== DUPLICATE TRANSACTIONS ===")
    if not duplicates:
        print("✔ No duplicates found")
    else:
        print("Duplicates:", duplicates)

    print("\n✅ RECONCILIATION COMPLETE\n")