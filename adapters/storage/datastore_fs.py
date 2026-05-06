from __future__ import annotations

import json
import pickle
from collections.abc import Mapping
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from core.services.runtime.datastore import DataStore, InvalidEventEnvelopeError
from core.services.runtime.event_codec import encode_datastore_event


class JSONLFileDataStore(DataStore):
    """
    Filesystem append-only store using JSONL.

    Layout:
      <root>/<scope>/<runtime_id>/
        order_events.jsonl
        fill_events.jsonl
        portfolio_snapshots.jsonl
        metrics.jsonl
    """

    def __init__(self, *, root_dir: Path, scope: str, runtime_id: str) -> None:
        super().__init__(scope=scope, runtime_id=runtime_id)
        self.root_dir = root_dir

    def _dir(self, *, create: bool) -> Path:
        d = self.root_dir / self.runtime_id
        if create:
            d.mkdir(parents=True, exist_ok=True)
        return d

    def _append_jsonl(self, filename: str, obj: Any) -> None:
        path = self._dir(create=True) / filename
        line = json.dumps(obj, ensure_ascii=False, default=str)
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def append_order_event(self, event: dict[str, Any], *, scope: str) -> None:
        self._assert_scope(scope)
        self._validate_event_envelope(event, scope=scope, expected_payload_type="order_event")
        self._append_jsonl("order_events.jsonl", event)

    def append_fill_event(self, event: dict[str, Any], *, scope: str) -> None:
        self._assert_scope(scope)
        self._validate_event_envelope(event, scope=scope, expected_payload_type="fill_event")
        self._append_jsonl("fill_events.jsonl", event)

    def append_roll_event(self, event: dict[str, Any], *, scope: str) -> None:
        self._assert_scope(scope)
        self._validate_event_envelope(event, scope=scope, expected_payload_type="roll")
        self._append_jsonl("roll_events.jsonl", event)

    def append_rank_event(self, event: dict[str, Any], *, scope: str) -> None:
        self._assert_scope(scope)
        self._validate_event_envelope(event, scope=scope, expected_payload_type="rank")
        self._append_jsonl("rank_events.jsonl", event)

    def append_strategy_score_event(self, event: dict[str, Any], *, scope: str) -> None:
        self._assert_scope(scope)
        self._validate_event_envelope(event, scope=scope, expected_payload_type="strategy_score")
        self._append_jsonl("strategy_score_events.jsonl", event)

    def append_order_lifecycle_event(self, event: dict[str, Any], *, scope: str) -> None:
        self._assert_scope(scope)
        self._validate_event_envelope(
            event,
            scope=scope,
            expected_payload_type="order_lifecycle",
        )
        self._append_jsonl("order_lifecycle_events.jsonl", event)

    def save_portfolio_snapshot(self, *, ts: int, portfolio: Any, scope: str) -> None:
        self._assert_scope(scope)
        base_dir = self._dir(create=True)
        snap_dir = base_dir / "snapshots"
        snap_dir.mkdir(parents=True, exist_ok=True)
        filename = f"portfolio_{ts}.pkl"
        rel_path = str(Path("snapshots") / filename)
        abs_path = snap_dir / filename
        with abs_path.open("wb") as f:
            pickle.dump(portfolio, f)
        event = encode_datastore_event(
            base={
                "ts": ts,
                "runtime_id": self.runtime_id,
                "scope": scope,
                "symbol": "",
                "strategy_name": "runtime_snapshot",
                "strategy_id": "runtime_snapshot",
                "strategy_impl": "DataStore",
            },
            event_type="snapshot",
            payload_type="snapshot",
            source="datastore",
            payload={
                "ts": ts,
                "portfolio_file": rel_path,
                "portfolio_repr": str(portfolio),
            },
        )
        self._validate_event_envelope(event, scope=scope, expected_payload_type="snapshot")
        self._append_jsonl("portfolio_snapshots.jsonl", event)


    def load_latest_portfolio_snapshot(self, *, scope: str) -> Any | None:
        self._assert_scope(scope)
        base_dir = self._dir(create=False)
        index_path = base_dir / "portfolio_snapshots.jsonl"
        if not index_path.exists():
            return None
        last = None
        with index_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    last = line
        if last is None:
            return None
        try:
            data = json.loads(last)
        except JSONDecodeError:
            return None
        if not isinstance(data, Mapping):
            return None
        try:
            snapshot = self._flatten_event_for_read(
                data,
                scope=scope,
                expected_payload_type="snapshot",
            )
        except InvalidEventEnvelopeError:
            return None
        rel = snapshot.get("portfolio_file")
        if not rel:
            return None
        abs_path = base_dir / rel
        if not abs_path.exists():
            return None
        with abs_path.open("rb") as f:
            return pickle.load(f)


    def _read_jsonl(
        self,
        filename: str,
        *,
        scope: str,
        expected_payload_type: str,
    ) -> list[dict[str, Any]]:
        path = self._dir(create=False) / filename
        if not path.exists():
            return []
        out: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except JSONDecodeError:
                    continue
                if not isinstance(event, Mapping):
                    continue
                try:
                    out.append(
                        self._flatten_event_for_read(
                            event,
                            scope=scope,
                            expected_payload_type=expected_payload_type,
                        )
                    )
                except InvalidEventEnvelopeError:
                    continue
        return out

    def read_order_events(self, *, scope: str) -> list[dict[str, Any]]:
        self._assert_scope(scope)
        return self._read_jsonl(
            "order_events.jsonl",
            scope=scope,
            expected_payload_type="order_event",
        )

    def read_fill_events(self, *, scope: str) -> list[dict[str, Any]]:
        self._assert_scope(scope)
        return self._read_jsonl(
            "fill_events.jsonl",
            scope=scope,
            expected_payload_type="fill_event",
        )

    def read_roll_events(self, *, scope: str) -> list[dict[str, Any]]:
        self._assert_scope(scope)
        return self._read_jsonl("roll_events.jsonl", scope=scope, expected_payload_type="roll")

    def read_rank_events(self, *, scope: str) -> list[dict[str, Any]]:
        self._assert_scope(scope)
        return self._read_jsonl("rank_events.jsonl", scope=scope, expected_payload_type="rank")

    def read_strategy_score_events(self, *, scope: str) -> list[dict[str, Any]]:
        self._assert_scope(scope)
        return self._read_jsonl(
            "strategy_score_events.jsonl",
            scope=scope,
            expected_payload_type="strategy_score",
        )

    def read_order_lifecycle_events(self, *, scope: str) -> list[dict[str, Any]]:
        self._assert_scope(scope)
        return self._read_jsonl(
            "order_lifecycle_events.jsonl",
            scope=scope,
            expected_payload_type="order_lifecycle",
        )

    def append_metrics(self, *, ts: int, metrics: Mapping[str, Any], scope: str) -> None:
        self._assert_scope(scope)
        event = encode_datastore_event(
            base={
                "ts": ts,
                "runtime_id": self.runtime_id,
                "scope": scope,
                "symbol": "",
                "strategy_name": "runtime_observation",
                "strategy_id": "runtime_observation",
                "strategy_impl": "DataStore",
            },
            event_type="observation",
            payload_type="observation",
            source="datastore",
            payload={"ts": ts, "metrics": dict(metrics)},
        )
        self._validate_event_envelope(event, scope=scope, expected_payload_type="observation")
        self._append_jsonl("metrics.jsonl", event)
