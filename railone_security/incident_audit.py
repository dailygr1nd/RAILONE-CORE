"""Redacted security-event reporting for sandbox admission boundaries.

No exception message or untrusted request body is written to the database.
The log is append-only at the application schema level, not an external WORM log.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4


class SecurityAuditWriter(Protocol):
    def record_rejection(
        self, *, event_type: str, operation: str, correlation_ref: str,
        error: Exception, at: datetime,
    ) -> None: ...


def rejection_code(error: Exception) -> str:
    """Bounded allowlist: never leak raw error strings into operational logs."""
    prefix = str(error).split(':', 1)[0]
    recognized = {
        "BILATERAL_SIGNATURE_INVALID", "BILATERAL_SIGNER_OWNER_MISMATCH",
        "RECEIVER_AUTHORITY_SCOPE_INVALID", "RECEIVER_QUOTE_BINDING_MISMATCH",
        "RECEIVER_AUTHORITY_NOT_ACTIVE", "BILATERAL_QUOTE_BINDING_MISMATCH",
        "BILATERAL_CHAIN_BROKEN", "BILATERAL_AUTHORITY_EXPIRED_OR_REORDERED",
        "BILATERAL_AUTHORITY_ID_MISMATCH", "BILATERAL_UTT_REQUIRED",
        "BILATERAL_RECEIVER_ACCEPTANCE_REQUIRED",
        "BILATERAL_P2P_AUTHORITIES_REQUIRED", "PROVIDER_REQUEST_DIGEST_MISMATCH",
        "BENEFICIARY_VERIFICATION_REQUIRED", "BENEFICIARY_VERIFICATION_MISMATCH",
        "BENEFICIARY_VERIFICATION_EXPIRED", "SENDER_FIRST_BILATERAL_V4_REQUIRED", "RECEIVER_FIRST_V2_DEPRECATED",
        "SENDER_AUTHORITY_SCOPE_INVALID", "SENDER_QUOTE_BINDING_MISMATCH",
        "SENDER_AUTHORITY_NOT_ACTIVE", "SENDER_FIRST_FLOW_P2P_ONLY",
        "PERSISTED_BILATERAL_AUTHORITIES_MISSING",
    }
    return prefix if prefix in recognized else "BOUNDARY_VALIDATION_REJECTED"
