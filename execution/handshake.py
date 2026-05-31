# ==========================================
# execution/handshake.py
# RailOne Execution Trust Handshake
# ==========================================

from audit import append_log

from crypto.token_factory import (
    TokenFactory
)

from execution.state_machine import (

    ExecutionContext,
    ExecutionState
)

from execution.checkpoint_engine import (
    create_checkpoint
)


# ==========================================
# RUN TRUST HANDSHAKE
# ==========================================
def run_handshake(

    sender_id: str,
    receiver_id: str,
    amount: float,
    currency: str = "KES",
    continuity_uid: str | None = None
):

    print(
        "\n🔐 Running Execution Trust Handshake..."
    )

    if not continuity_uid:

        raise ValueError(
            "continuity_uid required"
        )

    ctx = ExecutionContext(

        utt_id="HANDSHAKE_ONLY",

        rtt_id=None,

        continuity_uid=
            continuity_uid,

        sender_id=
            sender_id,

        receiver_id=
            receiver_id,

        amount=
            amount,

        currency=
            currency
    )

    # =====================================
    # IDENTITY VERIFIED
    # =====================================
    ctx.transition(
        ExecutionState.IDENTITY_VERIFIED
    )

    # =====================================
    # ETK-S
    # =====================================
    etk_s_bundle = (

        TokenFactory
        .generate_etk_s(

            sender_id,
            amount,
            currency
        )
    )

    etk_s = (
        etk_s_bundle["etk_s"]
    )

    ctx.transition(

        ExecutionState.INTENT_LOCKED,

        {
            "etk_s": etk_s
        }
    )

    # =====================================
    # ETK-R
    # =====================================
    etk_r_bundle = (

        TokenFactory
        .generate_etk_r(

            etk_s,
            receiver_id
        )
    )

    etk_r = (
        etk_r_bundle["etk_r"]
    )

    ctx.transition(

        ExecutionState.RECEIVER_CONFIRMED,

        {
            "etk_r": etk_r
        }
    )

    # =====================================
    # RTT
    # =====================================
    rtt_bundle = (

        TokenFactory
        .generate_rtt(

            etk_s,
            etk_r
        )
    )

    rtt_id = (
        rtt_bundle["rtt"]
    )

    ctx.rtt_id = rtt_id

    ctx.transition(

        ExecutionState.HANDSHAKE_VERIFIED,

        {
            "rtt_id":
                rtt_id
        }
    )

    # =====================================
    # ATTACH TRUST ARTIFACTS
    # =====================================
    ctx.attach(
        "etk_s",
        etk_s
    )

    ctx.attach(
        "etk_r",
        etk_r
    )

    ctx.attach(
        "rtt_id",
        rtt_id
    )

    # =====================================
    # CHECKPOINT
    # =====================================
    create_checkpoint(

        utt_id=
            "HANDSHAKE_ONLY",

        rtt_id=
            rtt_id,

        continuity_uid=
            continuity_uid,

        checkpoint_state=
            "HANDSHAKE_VERIFIED",

        snapshot=
            ctx.to_dict()
    )

    # =====================================
    # AUDIT
    # =====================================
    append_log(

        "HANDSHAKE_COMPLETE",

        {

            "continuity_uid":
                continuity_uid,

            "rtt_id":
                rtt_id,

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
        f"RTT: {rtt_id}"
    )

    return {

        "continuity_uid":
            continuity_uid,

        "etk_s":
            etk_s,

        "etk_r":
            etk_r,

        "rtt_id":
            rtt_id,

        "ctx":
            ctx.to_dict()
    }