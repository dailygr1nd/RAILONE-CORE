# Simulation.py
from transaction_engine import initiate_transaction
from user_accounts import (
    generate_accounts,
    get_account_balance,
)
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


def main():
    print("=== RAILONE PRODUCTION SIMULATOR ===")

    print("\n=== SENDER ONBOARDING ===")
    sender_name = input("Enter Full Name: ")
    sender_nid = input("Enter National ID: ")

    sender = onboard_user(
        sender_name,
        sender_nid,
        role="sender",
    )

    self_transfer = input(
        "\nSelf transfer? (y/n): "
    ).strip().lower()

    if self_transfer == "y":
        receiver = sender
        print("\n✅ Self-transfer mode enabled")
    else:
        print("\n=== RECEIVER ONBOARDING ===")
        receiver_name = input("Enter Full Name: ")
        receiver_nid = input("Enter National ID: ")

        receiver = onboard_user(
            receiver_name,
            receiver_nid,
            role="receiver",
        )

    sender_accounts = flatten_accounts(
        generate_accounts(sender_nid, "KE")
    )

    receiver_accounts = flatten_accounts(
        generate_accounts(receiver["nid"], "KE")
    )

    sender_acc = choose_account(
        sender_accounts,
        "SELECT DEBIT ACCOUNT",
    )

    receiver_acc = choose_account(
        receiver_accounts,
        "SELECT CREDIT ACCOUNT",
    )

    amount = float(input("\nEnter transfer amount: "))

    print("\n=== EXECUTING TRANSACTION ===")

    success, message, utt = initiate_transaction(
        sender_id=sender_nid,
        receiver_id=receiver["nid"],
        amount=amount,
        debit_account_id=sender_acc["account_id"],
        credit_account_id=receiver_acc["account_id"],
        sender_currency=sender_acc["currency"],
        receiver_currency=receiver_acc["currency"],
    )

    print("\n=== RESULT ===")
    print(f"Success: {success}")
    print(f"Message: {message}")
    print(f"UTT: {utt}")

    print("\n=== UPDATED BALANCES ===")
    print("\nSENDER")
    show_accounts(
        flatten_accounts(
            generate_accounts(sender_nid, "KE")
        )
    )

    if self_transfer != "y":
        print("\nRECEIVER")
        show_accounts(
            flatten_accounts(
                generate_accounts(receiver['nid'], 'KE')
            )
        )

    print("\n🧾 Logs written successfully")
    print("Audit log stored separately")
    print("Ledger stored separately")


if __name__ == "__main__":
    main()