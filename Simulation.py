# ==============================
# Simulation.py (FINAL CLEAN UX)
# ==============================

from ledger.db import Base, engine, SessionLocal
from ledger.ledger_service import apply_genesis
from reconciliation_engine import run_reconciliation
from transaction_engine import initiate_transaction
from ledger.bootstrap import bootstrap_fx_pools
bootstrap_fx_pools()


# --------------------------------
# INIT DB
# --------------------------------
Base.metadata.create_all(bind=engine)


def bootstrap_fx_pools():
    session = SessionLocal()

    pools = ["FX_POOL-KES", "FX_POOL-TZS", "FX_POOL-UGX"]

    for p in pools:
        apply_genesis(session, p, 1_000_000)

    session.commit()
    session.close()


# --------------------------------
# BOOTSTRAP USER ACCOUNTS
# --------------------------------
def bootstrap_user_accounts(railone_id):

    session = SessionLocal()

    accounts = [
        f"MPESA-{railone_id}-KES",
        f"BANK_KE-{railone_id}-KES",
        f"BANK_UG-{railone_id}-UGX",
        f"BANK_TZ-{railone_id}-TZS",
        f"SMOVE-{railone_id}-KES",
    ]

    for acc in accounts:
        apply_genesis(session, acc, 100000.0)

    session.commit()
    session.close()

    return accounts


# --------------------------------
# ACCOUNT DETAILS
# --------------------------------
def get_account_details(account_id, session):
    from ledger.models import Account

    acc = session.query(Account).filter_by(id=account_id).first()

    institution, _, currency = account_id.split("-")

    return {
        "id": account_id,
        "institution": institution,
        "currency": currency,
        "balance": acc.balance if acc else 0.0
    }


# --------------------------------
# DISPLAY ACCOUNTS
# --------------------------------
def show_accounts(accounts, selectable=True):

    session = SessionLocal()
    detailed = []

    title = "SELECT ACCOUNT" if selectable else "YOUR ACCOUNTS"
    print(f"\n=== {title} ===", flush=True)

    for i, acc in enumerate(accounts, 1):
        info = get_account_details(acc, session)
        detailed.append(info)

        print(
            f"{i}. {info['institution']} | {info['currency']} | "
            f"Available: {info['balance']:,.2f}"
        )

    session.close()

    if not selectable:
        return None

    while True:
        try:
            choice = int(input("Choose account number: ").strip())
            if 1 <= choice <= len(detailed):
                return detailed[choice - 1]["id"]
        except:
            pass

        print("⚠️ Invalid selection, try again.")


# --------------------------------
# MAIN FLOW
# --------------------------------
def main():

    print("\n=== RAILONE PRODUCTION SIMULATOR ===", flush=True)

    # -----------------------------
    # SENDER ONBOARDING
    # -----------------------------
    print("\n=== SENDER ONBOARDING ===", flush=True)

    sender_name = input("Enter Full Name: ").strip()
    sender_id = input("Enter National ID: ").strip()

    print("📤 Verifying identity...", flush=True)

    sender_railone_id = sender_id

    print("✅ Sender onboarded")
    print("🔐 RailOneID:", sender_railone_id)

    sender_accounts = bootstrap_user_accounts(sender_railone_id)

    # -----------------------------
    # RECEIVER
    # -----------------------------
    self_transfer = input("\nSelf transfer? (y/n): ").strip().lower() == "y"

    if self_transfer:
        receiver_accounts = sender_accounts
    else:
        print("\n=== RECEIVER ONBOARDING ===", flush=True)

        receiver_name = input("Enter Receiver Name: ").strip()
        receiver_id = input("Enter Receiver National ID: ").strip()

        print("📤 Verifying receiver...", flush=True)

        receiver_accounts = bootstrap_user_accounts(receiver_id)

        print("✅ Receiver onboarded")
        print("🔐 RailOneID:", receiver_id)

    # -----------------------------
    # SHOW ACCOUNTS
    # -----------------------------
    print("\n=== SENDER ACCOUNTS ===")
    show_accounts(sender_accounts, selectable=False)

    print("\n=== RECEIVER ACCOUNTS ===")
    show_accounts(receiver_accounts, selectable=False)

    # -----------------------------
    # RECON BEFORE
    # -----------------------------
    print("\n🔍 RUNNING RECON BEFORE TX")

    issues = run_reconciliation()
    if issues:
        print("❌ Ledger drift:")
        for i in issues:
            print(i)
        return
    else:
        print("✔ Ledger clean")

    # -----------------------------
    # SELECT ACCOUNTS
    # -----------------------------
    print("\n=== SELECT DEBIT ACCOUNT ===")
    sender = show_accounts(sender_accounts)

    print("\n=== SELECT CREDIT ACCOUNT ===")
    receiver = show_accounts(receiver_accounts)

    # -----------------------------
    # AMOUNT INPUT (SAFE)
    # -----------------------------
    while True:
        try:
            amount = float(input("Enter transfer amount: ").strip())
            if amount > 0:
                break
        except:
            pass
        print("⚠️ Invalid amount, try again.")

    # -----------------------------
    # EXECUTE
    # -----------------------------
    print("\n=== EXECUTING TRANSACTION ===")

    tx = initiate_transaction(
        sender_account=sender,
        receiver_account=receiver,
        amount=amount,
        sender_currency=sender.split("-")[-1],
        receiver_currency=receiver.split("-")[-1]
    )

    # -----------------------------
    # RESULT (SAFE)
    # -----------------------------
    print("\n=== TRANSACTION RESULT ===")
    print("TX ID:", tx.get("tx_id"))
    print("STATUS:", tx.get("status"))

    if tx.get("status") == "PENDING":
        eta = tx.get("estimated_settlement", {})
        print(
            "ETA:",
            f"{eta.get('min_minutes','?')}–{eta.get('max_minutes','?')} minutes"
        )
    else:
        print("REASON:", tx.get("reason", "UNKNOWN"))

    # -----------------------------
    # SMS OUTPUT
    # -----------------------------
    print("\n📩 === RAILONE SMS ===")

    if tx.get("status") == "PENDING":
        eta = tx.get("estimated_settlement", {})
        print(f"""
TX: {tx['tx_id']}
STATUS: {tx['status']}
AMOUNT: {amount}
ETA: {eta.get('min_minutes','?')}–{eta.get('max_minutes','?')} minutes
""")
    else:
        print(f"""
TX: {tx.get('tx_id')}
STATUS: FAILED
REASON: {tx.get('reason','UNKNOWN')}
""")

    print("\n🧾 Ledger updates occur asynchronously")

    # -----------------------------
    # RECON AFTER
    # -----------------------------
    print("\n🔍 RECON AFTER SUBMIT")

    issues = run_reconciliation()
    if issues:
        print("⚠️ Drift (expected pre-settlement):")
        for i in issues:
            print(i)
    else:
        print("✔ Ledger consistent")


# --------------------------------
# ENTRY
# --------------------------------
if __name__ == "__main__":
    main()