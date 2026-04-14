# handshake.py
from audit import append_log
from token_factory import TokenFactory
from state_machine import TransactionContext, TransactionState


def run_handshake(
    sender_id,
    receiver_id,
    amount,
    currency="KES",
    institution_id="R1CORE",
):
    print("\n🔐 Running Dual Handshake...")

    # Generate system-wide unique tx id
    utt = TokenFactory.generate_utt(institution_id)

    # Create tx context
    tx = TransactionContext(
        utt=utt,
        amount=amount,
        currency=currency,
        sender_id=sender_id,
        receiver_id=receiver_id,
    )

    # Step 1: sender lock
    etk_s = TokenFactory.generate_etk_s(sender_id, amount)
    tx.transition(TransactionState.SENDER_LOCKED)

    # Step 2: receiver confirmation
    etk_r = TokenFactory.generate_etk_r(etk_s, receiver_id)
    tx.transition(TransactionState.RECEIVER_CONFIRMED)

    # Step 3: handshake verification
    rtt = TokenFactory.generate_rtt(
        etk_s,
        etk_r,
        tx_context=utt,
    )
    tx.transition(TransactionState.HANDSHAKE_VERIFIED)

    # Audit log
    payload = {
        "utt": utt,
        "rtt": rtt,
        "etk_sender": etk_s,
        "etk_receiver": etk_r,
        "state": tx.state.value,
    }

    append_log("HANDSHAKE", payload)

    print("✅ Handshake complete")
    print("UTT:", utt)
    print("RTT:", rtt)

    return {
        "utt": utt,
        "rtt": rtt,
        "etk_s": etk_s,
        "etk_r": etk_r,
        "tx": tx,
    }