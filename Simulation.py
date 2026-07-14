# ==============================
# Simulation.py
# RailOne Execution Continuity
# Production Simulator
# ==============================

from ledger.db import SessionLocal

from ledger.models import (
    Account
)

from identity.user_service import (

    onboard_user,

    get_railone_id_by_national_id
)

from identity.user_directory import (
    list_users
)

from execution.application.execution_initiator import (
    initiate_execution
)

from execution.queue.execution_queue import (
    get_all_executions
)

from execution.orchestrator.replay_engine import (
    replay_execution
)


import sys
import uuid

from bootstrap import (
    bootstrap
)

from institutions.core_registry import (
    register_core
)

from settlement.quote_engine import (
    generate_quote
)


# ==========================================
# BOOTSTRAP NETWORK
# ==========================================
bootstrap()

register_core()


# ==========================================
# SAFE INPUT
# ==========================================
def safe_input(prompt):

    try:

        return input(prompt)

    except Exception:

        return ""


# ==========================================
# GET USER ACCOUNTS
# ==========================================
def get_accounts(railone_id):

    session = SessionLocal()

    try:

        return (

            session.query(Account)

            .filter(
                Account.id.contains(
                    railone_id
                )
            )

            .all()
        )

    finally:

        session.close()


# ==========================================
# PRINT ACCOUNTS
# ==========================================
def print_accounts(accounts):

    if not accounts:

        print(
            "\n❌ No accounts found\n"
        )

        return

    for i, acc in enumerate(accounts, 1):

        mirrored_state = (

            acc.mirrored_available_state
            or 0.0
        )

        execution_reservation = (

            acc.execution_reservation
            or 0.0
        )

        available_execution_capacity = (

            mirrored_state -
            execution_reservation
        )

        print(f"""

{i}. {acc.account_type} | {acc.currency}

   {acc.id}

   Mirrored Available State:
   {mirrored_state:,.2f}

   Execution Reservation:
   {execution_reservation:,.2f}

   Available Execution Capacity:
   {available_execution_capacity:,.2f}
""")


# ==========================================
# ACCOUNT SELECTION
# ==========================================
def choose_account(

    accounts,

    label
):

    if not accounts:

        return None

    print(
        f"\n🔽 Select {label} account"
    )

    for i, acc in enumerate(accounts, 1):

        print(
            f"{i}. "
            f"{acc.account_type} "
            f"({acc.currency})"
        )

    try:

        choice = (

            int(
                safe_input(
                    "\nEnter choice: "
                )
            ) - 1
        )

        return accounts[choice]

    except:

        print(
            "❌ Invalid selection"
        )

        return None


# ==========================================
# USERS DIRECTORY
# ==========================================
def show_users():

    print(
        "\n========================================"
    )

    print(
        "👥 USERS DIRECTORY"
    )

    print(
        "========================================\n"
    )

    users = list_users()

    if not users:

        print("No users found")

        return

    for i, u in enumerate(users, 1):

        print(
            f"{i}. "
            f"{u['railone_id']} | "
            f"{u['national_id']}"
        )


# ==========================================
# DASHBOARD
# ==========================================
def show_dashboard(railone_id):

    print(
        "\n========================================"
    )

    print(
        "👤 EXECUTION DASHBOARD"
    )

    print(
        "========================================"
    )

    accounts = get_accounts(
        railone_id
    )

    print_accounts(accounts)


# ==========================================
# EXECUTION HISTORY
# ==========================================
def show_history(railone_id):

    print(
        "\n========================================"
    )

    print(
        "📜 EXECUTION HISTORY"
    )

    print(
        "========================================"
    )

    try:

        executions = (
            get_all_executions()
        )

        user_executions = [

            execution

            for execution in executions

            if (
                railone_id
                in execution[
                    "sender_account"
                ]
            )

            or (

                railone_id
                in execution[
                    "receiver_account"
                ]
            )
        ]

        if not user_executions:

            print(
                "\nNo executions found\n"
            )

            return

        for execution in user_executions[-10:]:

            print(f"""

UTT ID:
{execution['utt_id']}

RTT ID:
{execution.get('rtt_id')}

FROM:
{execution['sender_account']}

TO:
{execution['receiver_account']}

AMOUNT:
{execution['amount']}
{execution['currency_from']}

STATE:
{execution['state']}

REPLAY GENERATION:
{execution.get('replay_generation')}
""")

    except Exception as e:

        print(
            f"❌ Failed to load "
            f"history: {str(e)}"
        )


# ==========================================
# SEND MONEY
# ==========================================
def send_money(railone_id):

    print(
        "\n========================================"
    )

    print(
        "💸 INITIATE EXECUTION"
    )

    print(
        "========================================"
    )

    accounts = get_accounts(
        railone_id
    )

    if not accounts:

        print(
            "❌ No accounts available"
        )

        return

    print("\n💼 Accounts:")

    print_accounts(accounts)

    sender = choose_account(

        accounts,

        "DEBIT"
    )

    if not sender:

        return

    # ==========================================
    # RECEIVER
    # ==========================================
    self_transfer = safe_input(

        "\n🔁 Self transfer? (y/n): "

    ).lower()

    if self_transfer == "y":

        receiver_id = railone_id

    else:

        receiver_national_id = (

            safe_input(
                "Enter receiver National ID: "
            )
        )

        receiver_id = (

            get_railone_id_by_national_id(
                receiver_national_id
            )
        )

        if not receiver_id:

            print(
                "❌ Receiver not found"
            )

            return

    receiver_accounts = (
        get_accounts(receiver_id)
    )

    if not receiver_accounts:

        print(
            "❌ Receiver has no accounts"
        )

        return

    print("\n💼 Receiver Accounts:")

    print_accounts(receiver_accounts)

    receiver = choose_account(

        receiver_accounts,

        "CREDIT"
    )

    if not receiver:

        return

    # ==========================================
    # EXECUTION VALUE
    # ==========================================
    try:

        amount = float(

            safe_input(
                "\n💰 Enter amount: "
            )
        )

    except:

        print(
            "❌ Invalid amount"
        )

        return

    if amount <= 0:

        print(
            "❌ Amount must be > 0"
        )

        return

    print(
        "\n🔎 Preparing execution...\n"
    )

    try:

        # ==========================================
        # GENERATE EXECUTION QUOTE
        # ==========================================
        quote = generate_quote(

            sender=
                railone_id,

            receiver=
                receiver_id,

            amount=
                amount,

            currency_from=
                sender.currency,

            currency_to=
                receiver.currency
        )

        if "error" in quote:

            print(
                f"\n❌ Quote failed: "
                f"{quote['error']}"
            )

            return

        print(
            "\n📊 EXECUTION QUOTE"
        )

        print(
            f"Route: "
            f"{quote['route']}"
        )

        print(
            f"Fee: "
            f"{quote['total_fee']}"
        )

        print(
            f"Receive Amount: "
            f"{quote['receive_amount']}"
        )

        confirm = safe_input(

            "\nProceed with execution? (y/n): "

        ).lower()

        if confirm != "y":

            print(
                "❌ Execution cancelled"
            )

            return

        # ==========================================
        # INITIATE EXECUTION
        # ==========================================
        result = initiate_execution(

            sender_account=
                sender.id,

            receiver_account=
                receiver.id,

            sender_id=
                railone_id,

            receiver_id=
                receiver_id,

            continuity_uid=
                railone_id.split("-")[-2],

            amount=
                amount,

            sender_currency=
                sender.currency,

            receiver_currency=
                receiver.currency,

            quote=
                quote,

            idempotency_key=
                str(uuid.uuid4())
        )

        print(
            "\n========================================"
        )

        print(
            "✅ EXECUTION RESULT"
        )

        print(
            "========================================"
        )

        print(result)

    except Exception as e:

        print(
            "\n❌ Execution failed"
        )

        print(
            f"Reason: {str(e)}"
        )


# ==========================================
# EXECUTION REPLAY
# ==========================================
def replay_menu():

    print(
        "\n========================================"
    )

    print(
        "🔁 EXECUTION REPLAY"
    )

    print(
        "========================================"
    )

    utt_id = safe_input(
        "\nEnter UTT ID: "
    )

    result = replay_execution(
        utt_id
    )

    print(result)


# ==========================================
# CONTINUITY RECONSTRUCTION
# ==========================================
def reconstruct_menu():

    print(
        "\n========================================"
    )

    print(
        "🧬 CONTINUITY RECONSTRUCTION"
    )

    print(
        "========================================"
    )

    continuity_uid = safe_input(
        "\nEnter Continuity UID: "
    )

    summarize_continuity(
        continuity_uid
    )


# ==========================================
# USER ONBOARDING
# ==========================================
print(
    "\n========================================"
)

print(
    "🧾 USER ONBOARDING"
)

print(
    "========================================"
)

name = input(
    "Enter Full Name: "
)

national_id = input(
    "Enter National ID: "
)

print(
    "\n📤 Verifying identity..."
)

user = onboard_user(

    name=name,

    national_id=national_id
)

railone_id = (
    user["railone_id"]
)

# ==========================================
# DEMO LIQUIDITY
# ==========================================
session = SessionLocal()

try:

    accounts = (

        session.query(Account)

        .filter(
            Account.id.contains(
                railone_id
            )
        )

        .all()
    )

    for acc in accounts:

        acc.mirrored_available_state = (
            500000.0
        )

    session.commit()

finally:

    session.close()

print("✅ User onboarded")

print(
    f"👤 Name: {name}"
)

print(
    f"🔐 RailOneID: "
    f"{railone_id}"
)


# ==========================================
# MAIN MENU
# ==========================================
def main():

    print(
        "\n=== RAILONE EXECUTION CONTINUITY SIMULATOR ==="
    )

    user_id = railone_id

    while True:

        print("""

==============================
1. Dashboard
2. Initiate Execution
3. Execution History
4. Users Directory
5. Replay Execution
6. Reconstruct Continuity
7. Exit
==============================

""")

        choice = safe_input(
            "Select option: "
        )

        if choice == "1":

            show_dashboard(user_id)

        elif choice == "2":

            send_money(user_id)

        elif choice == "3":

            show_history(user_id)

        elif choice == "4":

            show_users()

        elif choice == "5":

            replay_menu()

        elif choice == "6":

            reconstruct_menu()

        elif choice == "7":

            print(
                "\n👋 Exiting..."
            )

            sys.exit()

        else:

            print(
                "❌ Invalid option"
            )


# ==========================================
# ENTRY
# ==========================================
if __name__ == "__main__":

    main()