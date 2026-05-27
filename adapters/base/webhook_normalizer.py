from adapters.base.continuity_event import (
    ContinuityEvent
)

from adapters.base.replay_guard import (
    ReplayGuard
)

from datetime import datetime


class WebhookNormalizer:

    @staticmethod
    def normalize(
        provider: str,
        railone_execution_id: str,
        provider_reference: str,
        canonical_state: str,
        payload: dict
    ):

        replay_hash = (
            ReplayGuard.generate_execution_hash(
                payload
            )
        )

        return ContinuityEvent(

            railone_execution_id=(
                railone_execution_id
            ),

            provider=provider,

            provider_reference=(
                provider_reference
            ),

            canonical_state=(
                canonical_state
            ),

            event_timestamp=(
                datetime.utcnow()
            ),

            replay_safe_hash=(
                replay_hash
            ),

            raw_payload=payload
        )