from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from core.services.runtime.datastore import DataStore


@dataclass(frozen=True)
class _Snapshot:
    ts: int
    portfolio: Any


class MemoryDataStore(DataStore):
    """In-memory append-only datastore for contracts/tests."""

    def __init__(self, *, env: str, runtime_id: str) -> None:
        super().__init__(env=env, runtime_id=runtime_id)
        self.order_events: list[Any] = []
        self.fill_events: list[Any] = []
        self.snapshots: list[_Snapshot] = []
        self.metrics: list[tuple[int, Mapping[str, Any]]] = []

    def append_order_event(self, event: Any, *, env: str) -> None:
        self._assert_env(env)
        self.order_events.append(event)

    def append_fill_event(self, event: Any, *, env: str) -> None:
        self._assert_env(env)
        self.fill_events.append(event)

    def save_portfolio_snapshot(self, *, ts: int, portfolio: Any, env: str) -> None:
        self._assert_env(env)
        self.snapshots.append(_Snapshot(ts=ts, portfolio=portfolio))

    def load_latest_portfolio_snapshot(self, *, env: str) -> Any | None:
        self._assert_env(env)
        if not self.snapshots:
            return None
        return self.snapshots[-1].portfolio

    def append_metrics(self, *, ts: int, metrics: Mapping[str, Any], env: str) -> None:
        self._assert_env(env)
        self.metrics.append((ts, metrics))
