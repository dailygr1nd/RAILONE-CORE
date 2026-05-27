from datetime import datetime

from adapters.mpesa.adapter import (
    MpesaAdapter
)

from adapters.flutterwave.adapter import (
    FlutterwaveAdapter
)

from adapters.paystack.adapter import (
    PaystackAdapter
)

from execution.event_store import emit_event

from execution.checkpoint_engine import (
    create_checkpoint
)

from execution.state_machine import (
    transition_state
)

from adapters.base.replay_guard import (
    ReplayGuard
)


class ProviderOrchestrator:

    def __init__(self, config):

        self.providers = {

            "mpesa": MpesaAdapter(
                config["MPESA_SECRET"]
            ),

            "flutterwave": (
                FlutterwaveAdapter(
                    config["FLW_SECRET"]
                )
            ),

            "paystack": (
                PaystackAdapter(
                    config["PAYSTACK_SECRET"]
                )
            ),
        }

    def select_provider(
        self,
        execution_context
    ):

        currency = execution_context.get(
            "currency"
        )

        country = execution_context.get(
            "country"
        )

        channel = execution_context.get(
            "channel"
        )

        if (
            country == "KE"
            and channel == "mobile_money"
        ):

            return "mpesa"

        if currency in ["KES", "UGX", "TZS"]:

            return "flutterwave"

        return "paystack"

    def initiate_execution(
        self,
        utt_id,
        payload,
        execution_context
    ):

        provider_name = (
            self.select_provider(
                execution_context
            )
        )

        provider = self.providers[
            provider_name
        ]

        replay_hash = (
            ReplayGuard
            .generate_execution_hash(
                payload
            )
        )

        emit_event(

            utt_id=utt_id,

            event_type=(
                "EXECUTION_INITIATED"
            ),

            provider=provider_name,

            canonical_state=(
                "execution_initiated"
            ),

            replay_safe_hash=(
                replay_hash
            ),

            payload=payload
        )

        transition_state(
            utt_id,
            "INTENT_LOCKED"
        )

        response = (
            provider.initiate_execution(
                payload
            )
        )

        create_checkpoint(

            utt_id=utt_id,

            checkpoint_type=(
                "provider_dispatch"
            ),

            state_snapshot={

                "provider":
                    provider_name,

                "response":
                    response,

                "timestamp":
                    datetime.utcnow()
                    .isoformat()
            }
        )

        emit_event(

            utt_id=utt_id,

            event_type=(
                "PROVIDER_DISPATCHED"
            ),

            provider=provider_name,

            canonical_state=(
                "execution_acknowledged"
            ),

            payload=response
        )

        return {

            "railone_execution_id":
                utt_id,

            "provider":
                provider_name,

            "provider_response":
                response
        }

    def process_webhook(
        self,
        provider_name,
        payload
    ):

        provider = self.providers[
            provider_name
        ]

        continuity_event = (
            provider.normalize_webhook(
                payload
            )
        )

        emit_event(

            utt_id=(
                continuity_event
                .railone_execution_id
            ),

            event_type=(
                "PROVIDER_CALLBACK"
            ),

            provider=(
                continuity_event.provider
            ),

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

            payload=(
                continuity_event
                .raw_payload
            )
        )

        self._transition_from_canonical_state(
            continuity_event
        )

        create_checkpoint(

            utt_id=(

                continuity_event
                .railone_execution_id
            ),

            checkpoint_type=(
                "provider_callback"
            ),

            state_snapshot={

                "provider":

                    continuity_event
                    .provider,

                "provider_reference":

                    continuity_event
                    .provider_reference,

                "canonical_state":

                    continuity_event
                    .canonical_state,

                "timestamp":

                    continuity_event
                    .event_timestamp
                    .isoformat()
            }
        )

        return continuity_event

    def recover_execution(
        self,
        provider_name,
        execution_id
    ):

        provider = self.providers[
            provider_name
        ]

        emit_event(

            utt_id=execution_id,

            event_type=(
                "RECOVERY_INITIATED"
            ),

            provider=provider_name,

            canonical_state=(
                "execution_requires_recovery"
            )
        )

        recovery_response = (
            provider.recover_execution(
                execution_id
            )
        )

        create_checkpoint(

            utt_id=execution_id,

            checkpoint_type=(
                "execution_recovery"
            ),

            state_snapshot={
                "provider":
                    provider_name,

                "recovery_response":
                    recovery_response,

                "timestamp":
                    datetime.utcnow()
                    .isoformat()
            }
        )

        return recovery_response

    def reconcile_execution(
        self,
        provider_name,
        execution_id
    ):

        provider = self.providers[
            provider_name
        ]

        reconciliation_response = (
            provider.reconcile_execution(
                execution_id
            )
        )

        emit_event(

            utt_id=execution_id,

            event_type=(
                "RECONCILIATION_PERFORMED"
            ),

            provider=provider_name,

            payload=(
                reconciliation_response
            )
        )

        return reconciliation_response

    def _transition_from_canonical_state(
        self,
        continuity_event
    ):

        state_mapping = {

            "execution_settled":
                "SETTLED",

            "execution_reversed":
                "ROLLED_BACK",

            "execution_timeout":
                "REPLAY_REQUIRED",

            "execution_rejected":
                "FAILED",

            "execution_requires_recovery":
                (
                    "RECONCILIATION_PENDING"
                ),

            "execution_in_progress":
                "EXECUTION_CONFIRMED",
        }

        target_state = state_mapping.get(

            continuity_event
            .canonical_state
        )

        if target_state:

            transition_state(

                continuity_event
                .railone_execution_id,

                target_state
            )