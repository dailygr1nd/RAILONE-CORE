"""Production PostgreSQL repository adapters for the RailOne pilot runtime."""

from .runtime import PostgresDatabase, psycopg_connection_factory
from .identity import PostgresIdentityRepository
from .contracts import PostgresContractStore
from .execution import PostgresExecutionStore
from .operations import PostgresOperationsStore
from .history import PostgresTransactionHistoryStore
from .projection import PostgresProviderOutcomeProjectionStore
from .migrations import MigrationRunner
from .api_security import (
    PostgresApiAuditStore,
    PostgresRateLimitStore,
    PostgresTokenRevocationStore,
)

__all__ = [
    "PostgresDatabase",
    "PostgresContractStore",
    "PostgresExecutionStore",
    "PostgresOperationsStore",
    "PostgresTransactionHistoryStore",
    "PostgresProviderOutcomeProjectionStore",
    "MigrationRunner",
    "PostgresApiAuditStore",
    "PostgresRateLimitStore",
    "PostgresTokenRevocationStore",
    "PostgresIdentityRepository",
    "psycopg_connection_factory",
]
