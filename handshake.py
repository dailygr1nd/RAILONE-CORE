# ==============================
# handshake_engine.py (CLEAN — PROTOCOL CORRECT)
# ==============================

from audit import append_log
from token_factory import TokenFactory
from state_machine import TransactionContext, TransactionState


def run_handshake(
    sender_id: str,
    receiver_id: str,
    amount: float,
    currency: str = "KES",
    institution_id: str = "R1CORE",
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
    # 1. IDENTITY VERIFIED
    # --------------------------------
    ctx.transition(TransactionState.IDENTITY_VERIFIED)

    # --------------------------------
    # 2. ETK-S
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

    ctx.transition(TransactionState.INTENT_LOCKED)

    # --------------------------------
    # 3. ETK-R
    # --------------------------------
    etk_r, sig_r, payload_r = TokenFactory.generate_etk_r(
        etk_s,
        receiver_id,
        institution_id
    )

    if not TokenFactory.verify(payload_r, sig_r, institution_id):
        raise Exception("ETK-R SIGNATURE INVALID")

    if TokenFactory.is_expired(payload_s):
        raise Exception("HANDSHAKE EXPIRED")

    ctx.transition(TransactionState.RECEIVER_CONFIRMED)

    # --------------------------------
    # HANDSHAKE COMPLETE (NO RTT HERE)
    # --------------------------------
    ctx.transition(TransactionState.HANDSHAKE_VERIFIED)

    # --------------------------------
    # ATTACH
    # --------------------------------
    ctx.attach("etk_s", etk_s)
    ctx.attach("etk_r", etk_r)

    # --------------------------------
    # AUDIT
    # --------------------------------
    append_log("HANDSHAKE_COMPLETE", {
        "tx_id": tx_id,
        "etk_s": etk_s,
        "etk_r": etk_r,
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "amount": amount,
    })

    print("✅ Handshake complete")
    print("TX_ID:", tx_id)

    return {
        "tx_id": tx_id,
        "etk_s": etk_s,
        "etk_r": etk_r,
        "ctx": ctx.to_dict()
    }