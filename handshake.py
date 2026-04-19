# handshake.py

from audit import append_log
from token_factory import TokenFactory
from state_machine import (
    TransactionContext,
    TransactionState,
)


def run_handshake(
    sender_id,
    receiver_id,
    amount,
    currency="KES",
    institution_id="R1CORE",
):
    print("\n🔐 Running Dual Handshake...")

    tx = TransactionContext(
        utt=None,
        amount=amount,
        currency=currency,
        sender_id=sender_id,
        receiver_id=receiver_id,
    )

    # ETK-S
    etk_s = TokenFactory.generate_etk_s(
        sender_id,
        amount
    )
    tx.transition(TransactionState.SENDER_LOCKED)

    # ETK-R
    etk_r = TokenFactory.generate_etk_r(
        etk_s,
        receiver_id
    )
    tx.transition(
        TransactionState.RECEIVER_CONFIRMED
    )

    # RTT
    rtt = TokenFactory.generate_rtt(
        etk_s,
        etk_r,
        tx_context=sender_id + receiver_id,
    )

    tx.transition(
        TransactionState.HANDSHAKE_VERIFIED
    )

    # UTT LAST
    utt = TokenFactory.generate_utt(
        institution_id
    )

    tx.utt = utt

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