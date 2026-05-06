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

    def __init__(self, *, scope: str, runtime_id: str) -> None:
        super().__init__(scope=scope, runtime_id=runtime_id)
        self.order_events: list[dict[str, Any]] = []
        self.fill_events: list[dict[str, Any]] = []
        self.roll_events: list[dict[str, Any]] = []
        self.rank_events: list[dict[str, Any]] = []
        self.strategy_score_events: list[dict[str, Any]] = []
        self.order_lifecycle_events: list[dict[str, Any]] = []
        self.snapshots: list[_Snapshot] = []
        self.metrics: list[tuple[int, Mapping[str, Any]]] = []

    def append_order_event(self, event: dict[str, Any], *, scope: str) -> None:
        self._assert_scope(scope)
        self._validate_event_envelope(event, scope=scope, expected_payload_type="order_event")
        self.order_events.append(self._flatten_event_for_read(event))

    def append_fill_event(self, event: dict[str, Any], *, scope: str) -> None:
        self._assert_scope(scope)
        self._validate_event_envelope(event, scope=scope, expected_payload_type="fill_event")
        self.fill_events.append(self._flatten_event_for_read(event))

    def append_roll_event(self, event: dict[str, Any], *, scope: str) -> None:
        self._assert_scope(scope)
        self._validate_event_envelope(event, scope=scope, expected_payload_type="roll")
        self.roll_events.append(self._flatten_event_for_read(event))

    def append_rank_event(self, event: dict[str, Any], *, scope: str) -> None:
        self._assert_scope(scope)
        self._validate_event_envelope(event, scope=scope, expected_payload_type="rank")
        self.rank_events.append(self._flatten_event_for_read(event))

    def append_strategy_score_event(self, event: dict[str, Any], *, scope: str) -> None:
        self._assert_scope(scope)
        self._validate_event_envelope(event, scope=scope, expected_payload_type="strategy_score")
        self.strategy_score_events.append(self._flatten_event_for_read(event))

    def append_order_lifecycle_event(self, event: dict[str, Any], *, scope: str) -> None:
        self._assert_scope(scope)
        self._validate_event_envelope(
            event,
            scope=scope,
            expected_payload_type="order_lifecycle",
        )
        self.order_lifecycle_events.append(self._flatten_event_for_read(event))

    def save_portfolio_snapshot(self, *, ts: int, portfolio: Any, scope: str) -> None:
        self._assert_scope(scope)
        self.snapshots.append(_Snapshot(ts=ts, portfolio=portfolio))

    def load_latest_portfolio_snapshot(self, *, scope: str) -> Any | None:
        self._assert_scope(scope)
        if not self.snapshots:
            return None
        return self.snapshots[-1].portfolio

    def append_metrics(self, *, ts: int, metrics: Mapping[str, Any], scope: str) -> None:
        self._assert_scope(scope)
        self.metrics.append((ts, metrics))

    def read_order_events(self, *, scope: str) -> list[dict[str, Any]]:
        self._assert_scope(scope)
        return [self._flatten_event_for_read(event) for event in self.order_events]

    def read_fill_events(self, *, scope: str) -> list[dict[str, Any]]:
        self._assert_scope(scope)
        return [self._flatten_event_for_read(event) for event in self.fill_events]

    def read_roll_events(self, *, scope: str) -> list[dict[str, Any]]:
        self._assert_scope(scope)
        return [self._flatten_event_for_read(event) for event in self.roll_events]

    def read_rank_events(self, *, scope: str) -> list[dict[str, Any]]:
        self._assert_scope(scope)
        return [self._flatten_event_for_read(event) for event in self.rank_events]

    def read_strategy_score_events(self, *, scope: str) -> list[dict[str, Any]]:
        self._assert_scope(scope)
        return [self._flatten_event_for_read(event) for event in self.strategy_score_events]

    def read_order_lifecycle_events(self, *, scope: str) -> list[dict[str, Any]]:
        self._assert_scope(scope)
        return [
            self._flatten_event_for_read(event)
            for event in self.order_lifecycle_events
        ]
