# ==============================
# Simulation.py (UPDATED)
# ==============================

from ledger.init_db import init_db
from transaction_engine import initiate_transaction
from zk_sd import onboard_user
from reconciliation_engine import run_full_reconciliation

from ledger.db import SessionLocal
from ledger.models import Account

from bootstrap import bootstrap_settlement_accounts

bootstrap_settlement_accounts()


# ---------------------------------
# INIT
# ---------------------------------
init_db()

print("\n🔍 RUNNING FULL RECONCILIATION...")
run_full_reconciliation()


# ---------------------------------
# OBSERVABILITY
# ---------------------------------
def log_observation(event, data=None):
    print(f"\n📊 [{event}]")
    if data:
        for k, v in data.items():
            print(f"{k}: {v}")


# ---------------------------------
# GET USER ACCOUNTS
# ---------------------------------
def get_user_accounts(owner_id):
    session = SessionLocal()

    try:
        accounts = session.query(Account).filter_by(
            owner_id=owner_id,
            account_type="USER"
        ).all()

        result = []

        for acc in accounts:
            result.append({
                "provider": acc.provider,
                "account_id": acc.id,
                "currency": acc.currency,
                "available": round(acc.balance - acc.reserved, 2),
                "reserved": round(acc.reserved, 2)
            })

        return result

    finally:
        session.close()


# ---------------------------------
# PICKER
# ---------------------------------
def choose_account(accounts, title):
    print(f"\n=== {title} ===")

    for i, acc in enumerate(accounts, 1):
        print(
            f"{i}. {acc['provider']} | "
            f"{acc['account_id']} | "
            f"{acc['currency']} | "
            f"Available: {acc['available']:,.2f} | "
            f"Locked: {acc['reserved']:,.2f}"
        )

    while True:
        try:
            choice = int(input("\nChoose account number: "))
            if 1 <= choice <= len(accounts):
                return accounts[choice - 1]
            print("❌ Invalid selection")
        except ValueError:
            print("❌ Enter a valid number")


# ---------------------------------
# ONBOARD
# ---------------------------------
def safe_onboard(role):
    while True:
        print(f"\n=== {role.upper()} ONBOARDING ===")

        name = input("Enter Full Name: ")
        nid = input("Enter National ID: ")

        user = onboard_user(name, nid, role=role)

        if user:
            log_observation("USER_ONBOARDED", {
                "railone_id": user["railone_id"],
                "kyc": user["attestation"]["kyc_level"]
            })
            return user

        print("❌ Onboarding failed")


# ---------------------------------
# MAIN
# ---------------------------------
def main():
    print("\n=== RAILONE PRODUCTION SIMULATOR ===")

    sender = safe_onboard("sender")

    self_transfer = input("\nSelf transfer? (y/n): ").lower()

    if self_transfer == "y":
        receiver = sender
    else:
        receiver = safe_onboard("receiver")

    sender_accounts = get_user_accounts(sender["railone_id"])
    receiver_accounts = get_user_accounts(receiver["railone_id"])

    sender_acc = choose_account(sender_accounts, "SELECT DEBIT ACCOUNT")
    receiver_acc = choose_account(receiver_accounts, "SELECT CREDIT ACCOUNT")

    try:
        amount = float(input("\nEnter transfer amount: "))
    except:
        print("❌ Invalid amount")
        return

    print("\n=== EXECUTING TRANSACTION ===")

    tx = initiate_transaction(
        sender_account=sender_acc["account_id"],
        receiver_account=receiver_acc["account_id"],
        amount=amount,
        sender_currency=sender_acc["currency"],
        receiver_currency=receiver_acc["currency"]
    )

    # ---------------------------------
    # RESULT
    # ---------------------------------
    print("\n=== TRANSACTION RESULT ===")

    print(f"TX ID: {tx.get('tx_id')}")
    print(f"STATUS: {tx.get('status')}")

    if tx.get("status") == "PENDING":
        eta = tx.get("estimated_settlement", {})
        print(f"ETA: {eta.get('min_minutes')}–{eta.get('max_minutes')} minutes")

    if tx.get("reason"):
        print(f"Reason: {tx.get('reason')}")

    # ---------------------------------
    # OBSERVABILITY
    # ---------------------------------
    log_observation("TX_SUBMITTED", tx)

    # ---------------------------------
    # SMS
    # ---------------------------------
    print("\n📩 === RAILONE SMS ===")
    print(f"""
TX: {tx.get('tx_id')}
STATUS: {tx.get('status')}
AMOUNT: {amount}
ETA: 2–180 minutes
""")

    print("\n🧾 Ledger updates will occur asynchronously")


# ---------------------------------
if __name__ == "__main__":
    main()