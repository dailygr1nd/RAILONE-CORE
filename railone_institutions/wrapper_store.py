"""Append-only wrapper persistence contract and test implementation.

Stored wrappers are evidence only. Store acceptance does not authorize dispatch.
"""

from __future__ import annotations

from threading import RLock
from typing import Protocol

from datetime import datetime

from .wrapper import (AuthoritativeDispatchSnapshot, DispatchWrapperService, SignedDispatchWrapper)


class DispatchWrapperStore(Protocol):
    def put(self, signed: SignedDispatchWrapper, *, expected: AuthoritativeDispatchSnapshot, at: datetime) -> SignedDispatchWrapper: ...
    def require(self, rtt_id: str) -> SignedDispatchWrapper: ...


class InMemoryDispatchWrapperStore:
    def __init__(self, verifier: DispatchWrapperService) -> None:
        self._verifier = verifier
        self._lock = RLock()
        self._by_rtt: dict[str, SignedDispatchWrapper] = {}

    def put(self, signed: SignedDispatchWrapper, *, expected: AuthoritativeDispatchSnapshot, at: datetime) -> SignedDispatchWrapper:
        self._verifier.verify(signed, expected=expected, at=at)
        rtt_id = signed.wrapper.to_payload()["trace_identifiers"]["rtt_id"]
        with self._lock:
            existing = self._by_rtt.get(rtt_id)
            if existing is not None and (
                existing.wrapper != signed.wrapper
                or existing.signature.to_dict() != signed.signature.to_dict()
            ):
                raise ValueError("conflicting signed wrapper for one RTT")
            if existing is None:
                self._by_rtt[rtt_id] = signed
            return self._by_rtt[rtt_id]

    def require(self, rtt_id: str) -> SignedDispatchWrapper:
        with self._lock:
            try:
                return self._by_rtt[rtt_id]
            except KeyError as exc:
                raise LookupError("signed dispatch wrapper not found") from exc
