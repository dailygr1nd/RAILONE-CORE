# Simulation.py

from transaction_engine import initiate_transaction
from user_accounts import generate_accounts
from zk_sd import onboard_user


def flatten_accounts(accounts_dict):
    flat = []

    for provider, accounts in accounts_dict.items():
        for account_id, details in accounts.items():
            flat.append({
                "provider": provider,
                "account_id": account_id,
                "currency": details["currency"],
                "available": details["available"],
                "reserved": details["reserved"],
                "display_balance": (
                    f'{details["available"]} '
                    f'(locked: {details["reserved"]})'
                )
            })

    return flat


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
# SAFE ONBOARDING (BANK STYLE)
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
            print("🚫 Transaction aborted due to failed KYC.")
            exit()


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
    # ACCOUNTS
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
    # TRANSACTION EXECUTION
    # -----------------------------
    tx = initiate_transaction(
        sender_account=sender_acc["account_id"],
        receiver_account=receiver_acc["account_id"],
        amount=amount,
        corridor="LOCAL"
    )

    # -----------------------------
    # DERIVED VALUES (NO MORE PYLANCE ERRORS)
    # -----------------------------
    tx_id = tx.get("tx_id", "UNKNOWN")
    status = tx.get("status", "UNKNOWN")
    reason = tx.get("reason")
    route = tx.get("route")

    success = status.upper() in ["SUCCESS", "COMPLETED"]

    print("\n=== TRANSACTION RESULT ===")
    print(f"Transaction ID: {tx_id}")
    print(f"Status: {status}")

    if reason:
        print(f"Reason: {reason}")

    if route:
        print(f"Route: {route}")

    # -----------------------------
    # SMS SIMULATION OUTPUT
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
    print(f"UTT: {tx_id}")

    print("\n🧾 Ledger + Audit logs updated automatically")


if __name__ == "__main__":
    main()