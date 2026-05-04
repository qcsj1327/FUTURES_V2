from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from adapters.storage.datastore_fs import JSONLFileDataStore
from core.instruments.roll_policy import RollPolicy
from scripts.run_plan import main as run_plan_main
from tests.contracts.test_order_lifecycle_tracking_contracts import _write_lifecycle_plan


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_order_fill_lifecycle_events_share_required_identifiers(tmp_path: Path) -> None:
    rid = "rt_event_schema"
    plan_path = _write_lifecycle_plan(tmp_path, rid)

    assert run_plan_main(["--config", str(plan_path), "--runtime-id", rid, "--clean"]) == 0

    store_dir = tmp_path / "data" / "store" / "live" / rid
    orders = _read_jsonl(store_dir / "order_events.jsonl")
    fills = _read_jsonl(store_dir / "fill_events.jsonl")
    lifecycle = _read_jsonl(store_dir / "order_lifecycle_events.jsonl")

    assert orders
    assert fills
    assert lifecycle
    assert all(isinstance(ev.get("instrument_id"), str) and ev["instrument_id"] for ev in orders)
    assert all(
        isinstance(ev.get("trade_instrument_id"), str) and ev["trade_instrument_id"]
        for ev in orders
    )

    fill_ids = {ev.get("order_id") for ev in fills}
    lifecycle_ids = {ev.get("order_id") for ev in lifecycle}
    assert all(isinstance(order_id, str) and order_id for order_id in fill_ids)
    assert all(isinstance(order_id, str) and order_id for order_id in lifecycle_ids)
    assert fill_ids <= lifecycle_ids


def test_rank_event_schema_is_replayable(tmp_path: Path) -> None:
    rid = "rt_rank_schema"
    plan_path = _write_lifecycle_plan(tmp_path, rid)

    assert run_plan_main(["--config", str(plan_path), "--runtime-id", rid, "--clean"]) == 0

    events = _read_jsonl(tmp_path / "data" / "store" / "live" / rid / "rank_events.jsonl")
    assert events
    for ev in events:
        assert ev["event_type"] == "rank"
        assert ev["runtime_id"] == rid
        assert ev["env"] == "live"
        assert isinstance(ev["ts"], int)
        assert isinstance(ev["active_top_n"], int)
        assert isinstance(ev["excluded_symbols_count"], int)
        assert isinstance(ev["scores"], list)
        for item in ev["scores"]:
            assert isinstance(item, dict)
            assert isinstance(item.get("symbol"), str) and item["symbol"]
            assert isinstance(item.get("score"), int | float)


def test_roll_event_schema_is_replayable(tmp_path: Path) -> None:
    store = JSONLFileDataStore(root_dir=tmp_path / "live", env="live", runtime_id="rt_roll_schema")
    policy = RollPolicy(
        mode="fixed_main",
        contracts={"au": "SHFE.au2406"},
        runtime_id="rt_roll_schema",
        env="live",
        sink=store,
    )

    assert policy.resolve("au", 1) == "SHFE.au2406"
    policy.contracts["au"] = "SHFE.au2407"
    assert policy.resolve("au_main", 2) == "SHFE.au2407"

    events = store.read_roll_events(env="live")
    assert len(events) == 1
    ev = events[0]
    assert ev["event_type"] == "roll"
    assert ev["runtime_id"] == "rt_roll_schema"
    assert ev["base_symbol"] == "au"
    assert ev["from_contract"] == "SHFE.au2406"
    assert ev["to_contract"] == "SHFE.au2407"
    assert ev["ts"] == 2
    assert ev["reason"] == "fixed_main_contract_changed"
