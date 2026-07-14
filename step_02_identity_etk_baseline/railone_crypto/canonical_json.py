"""Strict deterministic JSON serialization for signed RailOne artifacts."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any


class CanonicalizationError(ValueError):
    """Raised when a payload cannot be represented canonically."""


_SCALAR_TYPES = (str, int, bool, type(None))


def _validate(value: Any, path: str = "$") -> None:
    if isinstance(value, float):
        raise CanonicalizationError(
            f"floating-point value is forbidden at {path}; use integer minor units"
        )

    if isinstance(value, _SCALAR_TYPES):
        return

    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise CanonicalizationError(
                    f"JSON object key must be a string at {path}"
                )
            _validate(child, f"{path}.{key}")
        return

    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        for index, child in enumerate(value):
            _validate(child, f"{path}[{index}]")
        return

    raise CanonicalizationError(
        f"unsupported value of type {type(value).__name__} at {path}"
    )


def canonical_json_bytes(value: Any) -> bytes:
    """Return a stable UTF-8 representation for RailOne-controlled JSON.

    This encoder intentionally supports a strict JSON subset. Financial values
    must be integer minor units, and timestamps must already be normalized to
    integer epoch seconds or UTC strings by the owning domain.
    """

    _validate(value)

    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise CanonicalizationError(str(exc)) from exc

    return encoded.encode("utf-8")
