from transaction_engine import onboard_user, select_account, execute_transaction
from audit import append_log
import time


def run_simulation():
    print("=== RAILONE PRODUCTION SIMULATOR ===\n")

    sender = onboard_user("sender")
    if not sender:
        return

    self_transfer = input("Self transfer? (y/n): ").strip().lower() == "y"

    if self_transfer:
        receiver = sender
    else:
        receiver = onboard_user("receiver")
        if not receiver:
            return

    sender_account = select_account(sender)
    receiver_account = select_account(receiver)

    if not sender_account or not receiver_account:
        print("❌ Account selection failed")
        return

    while True:
        amount_str = input("Amount to send: ").replace(",", "")
        try:
            amount = float(amount_str)
            if amount <= 0:
                raise ValueError
            break
        except ValueError:
            print("❌ Enter a valid positive amount.")

    etk_payload = {
        "etk_sender": sender["nid"],
        "etk_receiver": receiver["nid"]
    }
    etk_hash = append_log("HANDSHAKE", etk_payload)

    iso_payload = {
        "tx_id": f"RN-{int(time.time()*1000)}",
        "amount": amount,
        "currency": sender_account["currency"],
        "handshake_hash": etk_hash
    }
    append_log("ISO_MESSAGE", iso_payload)

    result = execute_transaction(
        sender,
        sender_account,
        receiver,
        receiver_account,
        amount,
    )

    print("\n✅ Simulation complete.")
    return result


if __name__ == "__main__":
    run_simulation()
