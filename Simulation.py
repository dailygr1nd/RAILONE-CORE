# Simulation.py

from ledger.init_db import init_db
from transaction_engine import initiate_transaction
from zk_sd import onboard_user

from reconciliation_engine import run_full_reconciliation

from ledger.db import SessionLocal
from ledger.models import Account


# ---------------------------------
# INIT SYSTEM
# ---------------------------------
init_db()

print("\n🔍 RUNNING FULL RECONCILIATION...")
run_full_reconciliation()


# ---------------------------------
# FETCH USER ACCOUNTS (CLEAN)
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
# ACCOUNT PICKER
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
            print("❌ Please enter a valid number")


# ---------------------------------
# SAFE ONBOARDING
# ---------------------------------
def safe_onboard(role):
    while True:
        print(f"\n=== {role.upper()} ONBOARDING ===")

        name = input("Enter Full Name: ")
        nid = input("Enter National ID: ")

        user = onboard_user(name, nid, role=role)

        if user is not None:
            return user

        print("\n❌ ONBOARDING FAILED")
        retry = input("Retry onboarding? (y/n): ").strip().lower()

        if retry != "y":
            print("🚫 Transaction aborted.")
            exit()


# ---------------------------------
# MAIN FLOW
# ---------------------------------
def main():
    print("\n=== RAILONE PRODUCTION SIMULATOR ===")

    # -----------------------------
    # SENDER
    # -----------------------------
    sender = safe_onboard("sender")

    self_transfer = input("\nSelf transfer? (y/n): ").strip().lower()

    # -----------------------------
    # RECEIVER
    # -----------------------------
    if self_transfer == "y":
        receiver = sender
        print("\n✅ Self-transfer mode enabled")
    else:
        receiver = safe_onboard("receiver")

    # -----------------------------
    # FETCH CLEAN USER ACCOUNTS
    # -----------------------------
    sender_accounts = get_user_accounts(sender["railone_id"])
    receiver_accounts = get_user_accounts(receiver["railone_id"])

    if not sender_accounts or not receiver_accounts:
        print("❌ No accounts found. Onboarding may have failed.")
        return

    sender_acc = choose_account(sender_accounts, "SELECT DEBIT ACCOUNT")
    receiver_acc = choose_account(receiver_accounts, "SELECT CREDIT ACCOUNT")

    # -----------------------------
    # INPUT AMOUNT
    # -----------------------------
    try:
        amount = float(input("\nEnter transfer amount: "))
    except ValueError:
        print("❌ Invalid amount")
        return

    print("\n=== EXECUTING TRANSACTION ===")

    # -----------------------------
    # EXECUTE TRANSACTION
    # -----------------------------
    tx = initiate_transaction(
        sender_account=sender_acc["account_id"],
        receiver_account=receiver_acc["account_id"],
        amount=amount,
        sender_currency=sender_acc["currency"],
        receiver_currency=receiver_acc["currency"]
    )

    # -----------------------------
    # RESULT DISPLAY
    # -----------------------------
    print("\n=== TRANSACTION RESULT ===")

    print(f"Transaction ID: {tx.get('tx_id')}")
    print(f"Status: {tx.get('status')}")

    if tx.get("reason"):
        print(f"Reason: {tx.get('reason')}")

    route = tx.get("route_result", {}).get("best_route", {})

    if route:
        print(f"Route: {route.get('rail')}")
        print(f"FX Rate: {route.get('fx_rate')}")
        print(f"Converted Amount: {route.get('converted_amount')}")

    print(f"Fees: {tx.get('fees')}")
    print(f"Net Amount: {tx.get('net_amount')}")

    # -----------------------------
    # SMS SIMULATION
    # -----------------------------
    print("\n📩 === RAILONE SMS NOTIFICATION ===")
    print(f"""
FROM: RailOne PAY
----------------------------------
TX: {tx.get('tx_id')}
STATUS: {tx.get('status')}
AMOUNT: {amount}
SENDER: {sender['nid']}
RECEIVER: {receiver['nid']}
----------------------------------
""")

    # -----------------------------
    # FINAL STATE
    # -----------------------------
    print("\n=== FINAL RESULT ===")
    print(f"Success: {tx.get('status') == 'SETTLED'}")
    print(f"UTT: {tx.get('utt')}")
    print(f"RTT: {tx.get('rtt')}")

    print("\n🧾 Ledger updated (source of truth)")


# ---------------------------------
# ENTRY POINT
# ---------------------------------
if __name__ == "__main__":
    main()