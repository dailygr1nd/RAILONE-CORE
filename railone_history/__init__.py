"""Permissioned UTT and continuity transaction-history projections."""

from .models import (
    READ_ANY_PERMISSION,
    AccessOutcome,
    SubjectKind,
    TransactionAccessAudit,
    TransactionHistoryEntry,
    TransactionHistoryPage,
    TransactionReadContext,
    TransactionRole,
    TransactionSubjectLink,
    UttTransactionProjection,
)
from .service import (
    TransactionAccessDeniedError,
    TransactionHistoryService,
    UttTransactionIndexer,
)
from .store import (
    InMemoryTransactionHistoryStore,
    TransactionProjectionNotFoundError,
)

__all__ = [
    "AccessOutcome",
    "InMemoryTransactionHistoryStore",
    "READ_ANY_PERMISSION",
    "SubjectKind",
    "TransactionAccessAudit",
    "TransactionAccessDeniedError",
    "TransactionHistoryEntry",
    "TransactionHistoryPage",
    "TransactionHistoryService",
    "TransactionProjectionNotFoundError",
    "TransactionReadContext",
    "TransactionRole",
    "TransactionSubjectLink",
    "UttTransactionIndexer",
    "UttTransactionProjection",
]
