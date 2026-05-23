# ==============================
# handshake.py
# RailOne Secure Dual Handshake
# Execution Trust Realization
# ==============================

from uuid import uuid4

from audit import (
    append_log
)

from token_factory import (
    TokenFactory
)

from execution.state_machine import (

    ExecutionContext,

    ExecutionState
)

from execution.event_emitter import (
    emit_event
)

from execution.checkpoint_engine import (
    create_checkpoint
)


# ==========================================
# RUN SECURE DUAL HANDSHAKE
# ==========================================
def run_handshake(

    sender_id: str,

    receiver_id: str,

    amount: float,

    currency: str = "KES",

    institution_id: str = "R1CORE",

    continuity_uid: str | None = None
):

    print(
        "\n🔐 Running Secure Dual Handshake..."
    )

    # ==========================================
    # CONTINUITY REQUIRED
    # ==========================================
    if not continuity_uid:

        raise ValueError(
            "continuity_uid required"
        )

    # ==========================================
    # EXECUTION CONTINUITY
    # ==========================================
    utt_id = (
        TokenFactory.generate_utt(
            institution_id
        )
    )

    # ==========================================
    # ROUTE REALIZATION THREAD
    # Initial RTT lineage placeholder
    # ==========================================
    rtt_id = (
        f"RTT-"
        f"{uuid4().hex[:12].upper()}"
    )

    # ==========================================
    # INITIAL EXECUTION CONTEXT
    # ==========================================
    ctx = ExecutionContext(

        utt_id=
            utt_id,

        rtt_id=
            rtt_id,

        continuity_uid=
            continuity_uid,

        amount=
            amount,

        currency=
            currency,

        sender_id=
            sender_id,

        receiver_id=
            receiver_id
    )

    # ==========================================
    # EXECUTION INIT EVENT
    # ==========================================
    emit_event(

        utt_id=
            utt_id,

        rtt_id=
            rtt_id,

        continuity_uid=
            continuity_uid,

        event_type=
            "HANDSHAKE_INITIATED",

        previous_state=
            None,

        new_state=
            ExecutionState.INIT.value
    )

    # ==========================================
    # IDENTITY VERIFIED
    # ==========================================
    ctx.transition(

        ExecutionState.IDENTITY_VERIFIED
    )

    # ==========================================
    # ETK-S
    # EXECUTION INTENT CAPTURE
    # ==========================================
    etk_s, sig_s, payload_s = (

        TokenFactory.generate_etk_s(

            sender_id,

            amount,

            institution_id
        )
    )

    # --------------------------------
    # VERIFY ETK-S
    # --------------------------------
    if not TokenFactory.verify(

        payload_s,

        sig_s,

        institution_id
    ):

        raise Exception(
            "ETK_S_SIGNATURE_INVALID"
        )

    if TokenFactory.is_expired(
        payload_s
    ):

        raise Exception(
            "ETK_S_EXPIRED"
        )

    # --------------------------------
    # EXECUTION INTENT LOCK
    # --------------------------------
    ctx.transition(

        ExecutionState.INTENT_LOCKED,

        {

            "etk_s":
                etk_s
        }
    )

    # ==========================================
    # ETK-R
    # RECEIVER EXECUTION CONFIRMATION
    # ==========================================
    etk_r, sig_r, payload_r = (

        TokenFactory.generate_etk_r(

            etk_s,

            receiver_id,

            institution_id
        )
    )

    # --------------------------------
    # VERIFY ETK-R
    # --------------------------------
    if not TokenFactory.verify(

        payload_r,

        sig_r,

        institution_id
    ):

        raise Exception(
            "ETK_R_SIGNATURE_INVALID"
        )

    if TokenFactory.is_expired(
        payload_r
    ):

        raise Exception(
            "HANDSHAKE_EXPIRED"
        )

    # --------------------------------
    # RECEIVER CONFIRMATION
    # --------------------------------
    ctx.transition(

        ExecutionState.RECEIVER_CONFIRMED,

        {

            "etk_r":
                etk_r
        }
    )

    # ==========================================
    # HANDSHAKE VERIFIED
    # ==========================================
    ctx.transition(

        ExecutionState.HANDSHAKE_VERIFIED
    )

    # ==========================================
    # ATTACH EXECUTION TRUST KEYS
    # ==========================================
    ctx.attach(

        "etk_s",

        etk_s
    )

    ctx.attach(

        "etk_r",

        etk_r
    )

    # ==========================================
    # CREATE HANDSHAKE CHECKPOINT
    # ==========================================
    create_checkpoint(

        utt_id=
            utt_id,

        rtt_id=
            rtt_id,

        continuity_uid=
            continuity_uid,

        checkpoint_state=
            "HANDSHAKE_VERIFIED",

        snapshot=
            ctx.to_dict()
    )

    # ==========================================
    # AUDIT
    # ==========================================
    append_log(

        "HANDSHAKE_COMPLETE",

        {

            "utt_id":
                utt_id,

            "rtt_id":
                rtt_id,

            "continuity_uid":
                continuity_uid,

            "etk_s":
                etk_s,

            "etk_r":
                etk_r,

            "sender_id":
                sender_id,

            "receiver_id":
                receiver_id,

            "amount":
                amount
        }
    )

    print(
        "✅ Handshake complete"
    )

    print(
        f"UTT ID: {utt_id}"
    )

    print(
        f"RTT ID: {rtt_id}"
    )

    return {

        # --------------------------------
        # EXECUTION CONTINUITY
        # --------------------------------
        "utt_id":
            utt_id,

        "rtt_id":
            rtt_id,

        "continuity_uid":
            continuity_uid,

        # --------------------------------
        # EXECUTION TRUST KEYS
        # --------------------------------
        "etk_s":
            etk_s,

        "etk_r":
            etk_r,

        # --------------------------------
        # EXECUTION CONTEXT
        # --------------------------------
        "ctx":
            ctx.to_dict()
    }