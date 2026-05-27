from datetime import datetime

from adapters.base.continuity_event import (
    ContinuityEvent
)

from adapters.base.replay_guard import (
    ReplayGuard
)

from .mapper import map_flutterwave_state


def normalize_flutterwave_webhook(payload):

    data = payload["data"]

    canonical_state = map_flutterwave_state(
        data["status"]
    )

    replay_hash = ReplayGuard.generate_execution_hash(
        data
    )

    return ContinuityEvent(

        railone_execution_id=data.get(
            "tx_ref"
        ),

        provider="flutterwave",

        provider_reference=str(
            data.get("id")
        ),

        canonical_state=canonical_state.value,

        event_timestamp=datetime.utcnow(),

        replay_safe_hash=replay_hash,

        raw_payload=payload
    )