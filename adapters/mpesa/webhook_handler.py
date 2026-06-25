from datetime import datetime

from adapters.base.webhook_normalizer import (
    WebhookNormalizer
)

from adapters.mpesa.mapper import (
    map_mpesa_state
)

from execution.events.event_store import (
    emit_event
)


def normalize_mpesa_callback(payload):

    callback = (
        payload
        .get("Body", {})
        .get("stkCallback", {})
    )

    result_code = str(
        callback.get("ResultCode", "-1")
    )

    canonical_state = (
        map_mpesa_state(
            result_code
        ).value
    )

    metadata_items = (

        callback
        .get("CallbackMetadata", {})
        .get("Item", [])
    )

    metadata = {}

    for item in metadata_items:

        key = item.get("Name")

        value = item.get("Value")

        metadata[key] = value

    provider_reference = metadata.get(
        "MpesaReceiptNumber",
        "UNKNOWN"
    )

    railone_execution_id = (
        callback.get(
            "CheckoutRequestID"
        )
    )

    continuity_event = (
        WebhookNormalizer.normalize(

            provider="mpesa",

            railone_execution_id=(
                railone_execution_id
            ),

            provider_reference=(
                provider_reference
            ),

            canonical_state=(
                canonical_state
            ),

            payload=payload
        )
    )

    emit_event(

        utt_id=(
            continuity_event
            .railone_execution_id
        ),

        event_type=(
            "MPESA_CALLBACK_RECEIVED"
        ),

        provider="mpesa",

        provider_reference=(
            continuity_event
            .provider_reference
        ),

        canonical_state=(
            continuity_event
            .canonical_state
        ),

        replay_safe_hash=(
            continuity_event
            .replay_safe_hash
        ),

        payload=payload
    )

    return continuity_event
