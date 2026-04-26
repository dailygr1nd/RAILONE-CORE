# ==============================
# Simulation.py (CLEAN + STABLE)
# ==============================

from ledger.db import SessionLocal
from ledger.models import Account

from user_service import onboard_user
from account_seed import seed_user_accounts

from transaction_engine import initiate_transaction
from execution_queue import get_all_tx

from user_service import get_railone_id_by_national_id

import sys

# --------------------------------
# UTIL
# --------------------------------
def safe_input(prompt):
    try:
        return input(prompt)
    except Exception:
        return ""


def get_accounts(user_id):
    session = SessionLocal()
    try:
        return session.query(Account).filter(Account.id.contains(user_id)).all()
    finally:
        session.close()


def print_accounts(accounts):
    if not accounts:
        print("\n❌ No accounts found\n")
        return

    for i, acc in enumerate(accounts, 1):
        available = acc.balance - acc.locked_balance

        print(f"""
{i}. {acc.account_type} | {acc.currency}
   {acc.id}
   Balance: {acc.balance:,.2f}
   Locked: {acc.locked_balance:,.2f}
   Available: {available:,.2f}
""")


def choose_account(accounts, label):
    if not accounts:
        return None

    print(f"\n🔽 Select {label} account")

    for i, acc in enumerate(accounts, 1):
        print(f"{i}. {acc.account_type} ({acc.currency})")

    try:
        choice = int(safe_input("\nEnter choice: ")) - 1
        return accounts[choice]
    except:
        print("❌ Invalid selection")
        return None


# --------------------------------
# DASHBOARD
# --------------------------------
def show_dashboard(user_id):
    print("\n========================================")
    print("👤 DASHBOARD")
    print("========================================")

    accounts = get_accounts(user_id)
    print_accounts(accounts)


# --------------------------------
# TRANSACTION HISTORY
# --------------------------------
def show_history(user_id):
    print("\n========================================")
    print("📜 TRANSACTION HISTORY")
    print("========================================")

    try:
        txs = get_all_tx()

        user_txs = [
            tx for tx in txs
            if user_id in tx["sender_account"] or user_id in tx["receiver_account"]
        ]

        if not user_txs:
            print("\nNo transactions found\n")
            return

        for tx in user_txs[-10:]:
            print(f"""
TX: {tx['tx_id']}
FROM: {tx['sender_account']}
TO: {tx['receiver_account']}
AMOUNT: {tx['amount']} {tx['currency_from']}
STATUS: {tx['status']}
""")

    except Exception as e:
        print(f"❌ Failed to load history: {str(e)}")


# --------------------------------
# SEND MONEY
# --------------------------------
def send_money(user_id):

    print("\n========================================")
    print("💸 SEND MONEY")
    print("========================================")

    accounts = get_accounts(user_id)

    if not accounts:
        print("❌ No accounts available")
        return

    print("\n💼 Accounts:")
    print_accounts(accounts)

    sender = choose_account(accounts, "DEBIT")
    if not sender:
        return

   
    receiver_nid = input("Enter receiver National ID: ")

    receiver_id = get_railone_id_by_national_id(receiver_nid)

    if not receiver_id:
      print("❌ Receiver not found")
    return

    receiver_accounts = get_accounts(receiver_id)

    if not receiver_accounts:
        print("❌ Receiver has no accounts")
        return

    print("\n💼 Receiver Accounts:")
    print_accounts(receiver_accounts)

    receiver = choose_account(receiver_accounts, "CREDIT")
    if not receiver:
        return

    try:
        amount = float(safe_input("\n💰 Enter amount: "))
    except:
        print("❌ Invalid amount")
        return

    if amount <= 0:
        print("❌ Amount must be > 0")
        return

    print("\n🔎 Processing transaction...\n")

    try:
        result = initiate_transaction(
            sender_account=sender.id,
            receiver_account=receiver.id,
            amount=amount,
            sender_currency=sender.currency,
            receiver_currency=receiver.currency
        )

        print("\n========================================")
        print("✅ RESULT")
        print("========================================")
        print(result)

    except Exception as e:
        print("\n❌ Something went wrong")
        print(f"Reason: {str(e)}")


# --------------------------------
# ONBOARD USER (LIGHTWEIGHT)
# --------------------------------

print("\n========================================")
print("🧾 USER ONBOARDING")
print("========================================")

name = input("Enter Full Name: ")
nid = input("Enter National ID: ")

print("\n📤 Verifying identity...")

railone_id = onboard_user(name, nid)

seed_user_accounts(railone_id)

print("✅ User onboarded")
print(f"👤 Name: {name}")
print(f"🔐 RailOneID: {railone_id}")

# --------------------------------
# MAIN MENU
# --------------------------------
def main():

    print("\n=== RAILONE PRODUCTION SIMULATOR ===")

    user_id = railone_id
    seed_user_accounts(user_id)

    while True:

        print("""
==============================
1. Dashboard
2. Send Money
3. Transaction History
4. Exit
==============================
""")

        choice = safe_input("Select option: ")

        if choice == "1":
            show_dashboard(user_id)

        elif choice == "2":
            send_money(user_id)

        elif choice == "3":
            show_history(user_id)

        elif choice == "4":
            print("\n👋 Exiting...")
            sys.exit()

        else:
            print("❌ Invalid option")


# --------------------------------
# ENTRY
# --------------------------------
if __name__ == "__main__":
    main()