# Simulation.py

from ledger.init_db import init_db
from transaction_engine import initiate_transaction
from user_accounts import generate_accounts
from zk_sd import onboard_user

from ledger.init_db import init_db
init_db()


# ---------------------------------
# ACCOUNT FLATTENER
# ---------------------------------
def flatten_accounts(accounts_dict):
    flat = []

    for provider, accounts in accounts_dict.items():
        for account_id, details in accounts.items():
            flat.append({
                "provider": provider,
                "account_id": account_id,
                "currency": details["currency"],
                "available": details["available"],
                "reserved": details["reserved"]
            })

    return flat

from ledger.account_service import ensure_account_exists

accounts = generate_accounts()

# 🔥 ADD HERE
for provider, provider_accounts in accounts.items():
    for acc_id, details in provider_accounts.items():
        ensure_account_exists(
            account_id=acc_id,
            provider=provider,
            currency=details["currency"],
            balance=details["available"]
        )

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
# MAIN
# ---------------------------------
def main():
    print("=== RAILONE PRODUCTION SIMULATOR ===")

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
    # AUTO ACCOUNT GENERATION
    # NO COUNTRY INPUT NEEDED
    # -----------------------------
    sender_accounts = flatten_accounts(
        generate_accounts(sender["nid"], "KE")
    )

    receiver_accounts = flatten_accounts(
        generate_accounts(receiver["nid"], "KE")
    )

    sender_acc = choose_account(sender_accounts, "SELECT DEBIT ACCOUNT")
    receiver_acc = choose_account(receiver_accounts, "SELECT CREDIT ACCOUNT")

    amount = float(input("\nEnter transfer amount: "))

    print("\n=== EXECUTING TRANSACTION ===")

    # -----------------------------
    # FIXED ENGINE CALL
    # PASS CURRENCIES DIRECTLY
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
    tx_id = tx.get("tx_id", "UNKNOWN")
    status = tx.get("status", "UNKNOWN")
    reason = tx.get("reason")

    route_result = tx.get("route_result", {})
    best_route = route_result.get("best_route", {})

    success = status == "SETTLED"

    print("\n=== TRANSACTION RESULT ===")
    print(f"Transaction ID: {tx_id}")
    print(f"Status: {status}")

    if reason:
        print(f"Reason: {reason}")

    if best_route:
        print(f"Best Route: {best_route.get('rail')}")
        print(f"FX Rate: {best_route.get('fx_rate')}")
        print(f"Converted Amount: {best_route.get('converted_amount')}")

    # -----------------------------
    # SMS SIMULATION
    # -----------------------------
    print("\n📩 === RAILONE SMS NOTIFICATIONS ===")

    print(f"""
FROM: RailOne PAY
----------------------------------
Transaction ID: {tx_id}
Status: {status}
Amount: {amount}
Sender: {sender['nid']}
Receiver: {receiver['nid']}
----------------------------------
""")

    # -----------------------------
    # FINAL RESULT
    # -----------------------------
    print("\n=== FINAL RESULT ===")
    print(f"Success: {success}")
    print(f"Message: {status}")
    print(f"UTT: {tx.get('utt')}")
    print(f"RTT: {tx.get('rtt')}")
    print(f"TX_ID: {tx.get('tx_id')}")

    print("\n🧾 Ledger + Audit logs updated automatically")


if __name__ == "__main__":
    main()