"""Small dependency-free metric surface for health and pilot assertions."""

from __future__ import annotations

from threading import RLock


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = RLock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], int] = {}

    def increment(self, name: str, **labels: str) -> None:
        if not name or any(not key or not value for key, value in labels.items()):
            raise ValueError("metric name and labels must be non-empty")
        key = (name, tuple(sorted(labels.items())))
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + 1

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
