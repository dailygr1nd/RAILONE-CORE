"""Execution-authority policy types."""

from enum import StrEnum


class ReceiverParticipationMode(StrEnum):
    ACTIVE_ACCEPTANCE = "ACTIVE_ACCEPTANCE"
    BENEFICIARY_PREAUTHORIZED = "BENEFICIARY_PREAUTHORIZED"
    DIRECTORY_RESOLUTION = "DIRECTORY_RESOLUTION"
    INTERNAL_MERCHANT_AUTHORITY = "INTERNAL_MERCHANT_AUTHORITY"
    PASSIVE_CREDIT = "PASSIVE_CREDIT"

    @property
    def receiver_confirmed(self) -> bool:
        return self is ReceiverParticipationMode.ACTIVE_ACCEPTANCE
