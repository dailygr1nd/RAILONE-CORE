# ==============================
# Simulation.py (PRODUCT FLOW)
# ==============================

from uuid import uuid4

from transaction_engine import initiate_transaction
from quote_engine import generate_quote
from revenue_db import get_total_revenue, get_revenue_breakdown


def show_accounts(accounts):

    print("\n=== YOUR ACCOUNTS ===")
    for i, acc in enumerate(accounts, 1):
        print(
            f"{i}. {acc['institution']} | {acc['currency']} | "
            f"{acc['id']} | Balance: {acc['balance']:.2f}"
        )


def select_account(accounts):

    choice = int(input("Choose account number: "))
    return accounts[choice - 1]["id"], accounts[choice - 1]["currency"]


def main():

    print("\n=== RAILONE SIMULATOR (PRODUCT MODE) ===")

    sender = "MPESA-10000891-KES"
    receiver = "BANK_KE-10000891-KES"

    sender_ccy = "KES"
    receiver_ccy = "KES"

    amount = float(input("\nEnter transfer amount: "))

    # -----------------------------
    # QUOTE
    # -----------------------------
    print("\n🔎 Generating quote...\n")

    quote = generate_quote(
        sender,
        receiver,
        amount,
        sender_ccy,
        receiver_ccy
    )

    if "error" in quote:
        print("❌", quote["error"])
        return

    print("=== QUOTE ===")
    print(f"Route: {quote['route']}")
    print(f"Send: {quote['send_amount']}")
    print(f"Receive: {quote['receive_amount']}")
    print(f"Fee: {quote['fee']}")
    print(f"Profit: {quote['profit']}")

    confirm = input("\nConfirm? (y/n): ")

    if confirm != "y":
        print("❌ Cancelled")
        return

    # -----------------------------
    # EXECUTE
    # -----------------------------
    tx = initiate_transaction(
        sender,
        receiver,
        amount,
        sender_ccy,
        receiver_ccy,
        quote=quote,
        idempotency_key=str(uuid4())
    )

    print("\n=== RESULT ===")
    print(tx)

    # -----------------------------
    # REVENUE DASHBOARD
    # -----------------------------
    print("\n💰 TOTAL REVENUE:", get_total_revenue())

    print("\n📊 BREAKDOWN:")
    breakdown = get_revenue_breakdown()
    for row in breakdown:
        print(row)


if __name__ == "__main__":
    main()