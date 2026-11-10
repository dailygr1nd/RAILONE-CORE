"""Bounded, low-cardinality sandbox counters (never transaction telemetry).

Names and labels are intentionally closed. Never pass UTT, RTT, account,
identity, endpoint, secret, or partner pricing material to this surface.
"""

from __future__ import annotations

from threading import RLock

from .models import EffectScenario

# Each metric has exactly these label keys.  A typo cannot create a new series.
_LABELS: dict[str, frozenset[str]] = {
    "railone_sandbox_submit_replay_total": frozenset({"provider"}),
    "railone_sandbox_submissions_total": frozenset({"provider", "outcome", "scenario"}),
    "railone_sandbox_effects_total": frozenset({"provider", "effect_type"}),
    "railone_sandbox_effect_requeues_total": frozenset(),
    "railone_sandbox_worker_failures_total": frozenset({"provider", "effect_type"}),
    "railone_sandbox_worker_applied_total": frozenset({"provider", "effect_type"}),
}
_OUTCOMES = frozenset({"ACCEPTED", "REJECTED", "UNKNOWN"})
_EFFECT_TYPES = frozenset({"SETTLED", "TIMEOUT", "REJECTED"})
_SCENARIOS = frozenset(s.value for s in EffectScenario)


class MetricsRegistry:
    """Confined to a synthetic sandbox with explicitly approved provider IDs."""

    def __init__(self, *, allowed_providers: tuple[str, ...] = ("BANK-KE", "MPESA-KE"),
                 max_series: int = 256) -> None:
        if not isinstance(max_series, int) or isinstance(max_series, bool) or not 1 <= max_series <= 4096:
            raise ValueError("metrics series budget is outside policy")
        providers = frozenset(allowed_providers)
        if not providers or len(providers) > 32 or any(
            not isinstance(p, str) or p not in {"BANK-KE", "MPESA-KE"} for p in providers
        ):
            raise ValueError("sandbox metrics require approved synthetic providers")
        self._allowed_providers = providers
        self._max_series = max_series
        self._lock = RLock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], int] = {}

    def increment(self, name: str, **labels: str) -> None:
        expected_keys = _LABELS.get(name)
        if expected_keys is None or set(labels) != expected_keys:
            raise ValueError("unapproved metric name or label keys")
        for key, value in labels.items():
            approved = {
                "provider": self._allowed_providers,
                "outcome": _OUTCOMES,
                "scenario": _SCENARIOS,
                "effect_type": _EFFECT_TYPES,
            }[key]
            if not isinstance(value, str) or value not in approved:
                raise ValueError("unapproved sandbox metric label value")
        series = (name, tuple(sorted(labels.items())))
        with self._lock:
            if series not in self._counters and len(self._counters) >= self._max_series:
                raise ValueError("sandbox metrics series budget exhausted")
            self._counters[series] = self._counters.get(series, 0) + 1

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                self._format(name, labels): value
                for (name, labels), value in sorted(self._counters.items())
            }

    @staticmethod
    def _format(name: str, labels: tuple[tuple[str, str], ...]) -> str:
        if not labels:
            return name
        return name + "{" + ",".join(f'{key}="{value}"' for key, value in labels) + "}"
