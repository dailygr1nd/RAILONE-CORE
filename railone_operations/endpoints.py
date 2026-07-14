"""Secure account-binding resolution boundary for provider dispatch."""

from __future__ import annotations

from threading import RLock
from typing import Protocol


class AccountEndpointResolver(Protocol):
    def resolve(self, *, institution_id: str, account_binding_id: str) -> str: ...


class InMemoryAccountEndpointResolver:
    """Test-only resolver. Production uses an isolated encrypted token vault."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._references: dict[tuple[str, str], str] = {}

    def register(
        self, *, institution_id: str, account_binding_id: str, provider_reference: str
    ) -> None:
        if not all(
            isinstance(value, str) and value.strip()
            for value in (institution_id, account_binding_id, provider_reference)
        ):
            raise ValueError("endpoint resolution values are required")
        key = (institution_id, account_binding_id)
        with self._lock:
            if key in self._references:
                raise ValueError("endpoint resolution already exists")
            self._references[key] = provider_reference

    def resolve(self, *, institution_id: str, account_binding_id: str) -> str:
        with self._lock:
            value = self._references.get((institution_id, account_binding_id))
            if value is None:
                raise LookupError("provider endpoint is not resolvable")
            return value
