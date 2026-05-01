from __future__ import annotations

import json
import pickle
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from core.services.runtime.datastore import DataStore


class JSONLFileDataStore(DataStore):
    """
    Filesystem append-only store using JSONL.

    Layout:
      <root>/<env>/<runtime_id>/
        order_events.jsonl
        fill_events.jsonl
        portfolio_snapshots.jsonl
        metrics.jsonl
    """

    def __init__(self, *, root_dir: Path, env: str, runtime_id: str) -> None:
        super().__init__(env=env, runtime_id=runtime_id)
        self.root_dir = root_dir

    def _dir(self) -> Path:
        d = self.root_dir / self.runtime_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _append_jsonl(self, filename: str, obj: Any) -> None:
        path = self._dir() / filename
        line = json.dumps(obj, ensure_ascii=False, default=str)
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def append_order_event(self, event: Any, *, env: str) -> None:
        self._assert_env(env)
        self._append_jsonl("order_events.jsonl", event)

    def append_fill_event(self, event: Any, *, env: str) -> None:
        self._assert_env(env)
        self._append_jsonl("fill_events.jsonl", event)

    def save_portfolio_snapshot(self, *, ts: int, portfolio: Any, env: str) -> None:
        self._assert_env(env)
        base_dir = self._dir()
        snap_dir = base_dir / "snapshots"
        snap_dir.mkdir(parents=True, exist_ok=True)
        filename = f"portfolio_{ts}.pkl"
        rel_path = str(Path("snapshots") / filename)
        abs_path = snap_dir / filename
        with abs_path.open("wb") as f:
            pickle.dump(portfolio, f)
        self._append_jsonl(
            "portfolio_snapshots.jsonl",
            {"ts": ts, "portfolio_file": rel_path, "portfolio_repr": str(portfolio)},
        )


    def load_latest_portfolio_snapshot(self, *, env: str) -> Any | None:
        self._assert_env(env)
        base_dir = self._dir()
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
        data = json.loads(last)
        rel = data.get("portfolio_file")
        if not rel:
            return None
        abs_path = base_dir / rel
        if not abs_path.exists():
            return None
        with abs_path.open("rb") as f:
            return pickle.load(f)


    def append_metrics(self, *, ts: int, metrics: Mapping[str, Any], env: str) -> None:
        self._assert_env(env)
        self._append_jsonl("metrics.jsonl", {"ts": ts, "metrics": dict(metrics)})
