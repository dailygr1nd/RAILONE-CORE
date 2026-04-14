# Simulation.py

from transaction_engine import initiate_transaction
from user_accounts import generate_accounts
from zk_sd import onboard_user


def flatten_accounts(accounts):
    flat = []

    for rail_name, rail_accounts in accounts.items():
        for acc_id, details in rail_accounts.items():
            flat.append(
                {
                    "rail": rail_name,
                    "account_id": acc_id,
                    "currency": details["currency"],
                    "balance": details["balance"],
                }
            )

    return flat


def choose_account(accounts, title):
    print(f"\n=== {title} ===")

    for i, acc in enumerate(accounts, 1):
        print(
            f"{i}. {acc['account_id']} | "
            f"{acc['currency']} "
            f"{acc['balance']:,.2f}"
        )

    idx = int(input("\nChoose account number: ")) - 1
    return accounts[idx]


def show_accounts(accounts):
    for acc in accounts:
        print(
            f"{acc['account_id']} | "
            f"{acc['currency']} "
            f"{acc['balance']:,.2f}"
        )


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
    success, message, utt = initiate_transaction(
        sender_id=sender["nid"],
        receiver_id=receiver["nid"],
        amount=amount,
        debit_account_id=sender_acc["account_id"],
        credit_account_id=receiver_acc["account_id"],
        sender_currency=sender_acc["currency"],
        receiver_currency=receiver_acc["currency"],
    )

    # -----------------------------
    # SMS SIMULATION OUTPUT
    # -----------------------------
    print("\n📩 === RAILONE SMS NOTIFICATIONS ===")

    print(f"""
    FROM: RailOne PAY
    ----------------------------------
    Transaction ID: {utt}
    Status: {message}
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
    print(f"Message: {message}")
    print(f"UTT: {utt}")

    print("\n🧾 Ledger + Audit logs updated automatically")


if __name__ == "__main__":
    main()