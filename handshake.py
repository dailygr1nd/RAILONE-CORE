# ==============================
# handshake_engine.py (FINAL)
# ==============================

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

    print("\n🔐 Running Secure Dual Handshake...")

    # --------------------------------
    # INIT CONTEXT
    # --------------------------------
    tx_id = TokenFactory.generate_tx_id(institution_id)

    ctx = TransactionContext(
        tx_id=tx_id,
        amount=amount,
        currency=currency,
        sender_id=sender_id,
        receiver_id=receiver_id,
    )

    # --------------------------------
    # ETK-S
    # --------------------------------
    etk_s, sig_s, payload_s = TokenFactory.generate_etk_s(
        sender_id,
        amount,
        institution_id
    )

    if not TokenFactory.verify(payload_s, sig_s, institution_id):
     raise Exception("ETK-S SIGNATURE INVALID")

    if TokenFactory.is_expired(payload_s):
     raise Exception("ETK-S EXPIRED")

    ctx.transition(TransactionState.SENDER_LOCKED)

    # --------------------------------
    # ETK-R
    # --------------------------------
    etk_r, sig_r, payload_r = TokenFactory.generate_etk_r(
        etk_s,
        receiver_id,
        institution_id
    )

    if not TokenFactory.verify(payload_r, sig_r, institution_id):
     raise Exception("ETK-R SIGNATURE INVALID")

    if TokenFactory.is_expired(payload_s):  # still tied to original intent
     raise Exception("HANDSHAKE EXPIRED")

    ctx.transition(TransactionState.RECEIVER_CONFIRMED)

    # --------------------------------
    # RTT
    # --------------------------------
    rtt, sig_rtt, payload_rtt = TokenFactory.generate_rtt(
        etk_s,
        etk_r,
        tx_id,
        institution_id
    )

    if not TokenFactory.verify(payload_rtt, sig_rtt, institution_id):
        raise Exception("RTT SIGNATURE INVALID")

    ctx.transition(TransactionState.HANDSHAKE_VERIFIED)

   
    # --------------------------------
    # AUDIT LOG
    # --------------------------------
    payload = {
        "tx_id": tx_id,
        "rtt": rtt,
        "etk_s": etk_s,
        "etk_r": etk_r,
        "signatures": {
            "etk_s": sig_s.hex(),
            "etk_r": sig_r.hex(),
            "rtt": sig_rtt.hex()
        },
        "state": ctx.state.value,
    }

    append_log("HANDSHAKE_SECURE", payload)

    print("✅ Secure Handshake complete")
    print("TX_ID:", tx_id)
    print("RTT:", rtt)

    return {
        "tx_id": tx_id,
        "rtt": rtt,
        "rtt_signature": sig_rtt.hex(), 
        "etk_s": etk_s,
        "etk_r": etk_r,
        "ctx": ctx,
    }