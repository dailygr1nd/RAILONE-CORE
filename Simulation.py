# Simulation.py
from pprint import pprint
from datetime import datetime, UTC

from zk_sd import onboard_user
from transaction_engine import TransactionEngine
from ledger import view_ledger
from audit import load_logs



engine = TransactionEngine()


# --------------------------
# HELPER FUNCTIONS
# --------------------------
def print_accounts(user):
    print("\n=== USER ACCOUNTS ===")

    accounts = user.get("accounts", {})

    for rail, rail_accounts in accounts.items():
        print(f"\n[{rail}]")

        for acc_id, details in rail_accounts.items():
            currency = details["currency"]
            balance = details["balance"]

            print(
                f"{acc_id} | {currency} {balance:,.2f}"
            )


def choose_account(user, label):
    accounts = user["accounts"]

    flat_accounts = []

    print(f"\n=== SELECT {label} ACCOUNT ===")

    idx = 1

    for rail, rail_accounts in accounts.items():
        for acc_id, details in rail_accounts.items():
            print(
                f"{idx}. {acc_id} | "
                f"{details['currency']} "
                f"{details['balance']:,.2f}"
            )

            flat_accounts.append((acc_id, details))
            idx += 1

    choice = int(input("\nChoose account number: ")) - 1

    return flat_accounts[choice][0]


def extract_currency(user, account_id):
    for rail_accounts in user["accounts"].values():
        if account_id in rail_accounts:
            return rail_accounts[account_id]["currency"]

    return None


# --------------------------
# MAIN SIMULATION FLOW
# --------------------------
def run_simulation():
    print("\n=== RAILONE PRODUCTION SIMULATOR ===")

    # --------------------------
    # ONBOARD USERS
    # --------------------------
    sender = onboard_user("sender")

    if not sender:
        print("Sender onboarding failed.")
        return

    receiver = onboard_user("receiver")

    if not receiver:
        print("Receiver onboarding failed.")
        return

    # --------------------------
    # DISPLAY USERS
    # --------------------------
    print("\n=== SENDER ===")
    print(f"RailOneID: {sender['railone_id']}")
    print_accounts(sender)

    print("\n=== RECEIVER ===")
    print(f"RailOneID: {receiver['railone_id']}")
    print_accounts(receiver)

    # --------------------------
    # ACCOUNT SELECTION
    # --------------------------
    debit_account = choose_account(sender, "DEBIT")
    credit_account = choose_account(receiver, "CREDIT")

    sender_currency = extract_currency(sender, debit_account)
    receiver_currency = extract_currency(receiver, credit_account)

    # --------------------------
    # AMOUNT INPUT
    # --------------------------
    amount = float(input("\nEnter transfer amount: "))

    # --------------------------
    # EXECUTE TRANSACTION
    # --------------------------
    print("\n=== EXECUTING TRANSACTION ===")

    try:
        success, message, utt = engine.create_transaction(
            sender_id=sender["nid"],
            receiver_id=receiver["nid"],
            amount=amount,
            debit_account_id=debit_account,
            credit_account_id=credit_account,
            sender_currency=sender_currency,
            receiver_currency=receiver_currency,
        )

        print("\n=== RESULT ===")
        print(f"Success: {success}")
        print(f"Message: {message}")
        print(f"UTT: {utt}")

    except Exception as e:
        print("\n=== ENGINE FAILURE ===")
        print(f"Error: {str(e)}")
        return

    # --------------------------
    # POST TX BALANCES
    # --------------------------
    print("\n=== UPDATED BALANCES ===")
    print("\nSENDER")
    print_accounts(sender)

    print("\nRECEIVER")
    print_accounts(receiver)

    # --------------------------
    # LEDGER VIEW
    # --------------------------
    print("\n=== IMMUTABLE LEDGER ===")

    ledger = view_ledger()

    for entry in ledger:
        pprint(entry)

 # --------------------------
# AUDIT LOGS
# --------------------------
print("\n=== AUDIT LOGS ===")

try:
    logs = load_logs()

    for log in logs[-5:]:
        pprint(log)

except Exception as e:
    print(f"No logs available: {e}")


# --------------------------
# ENTRYPOINT
# --------------------------
if __name__ == "__main__":
    run_simulation()