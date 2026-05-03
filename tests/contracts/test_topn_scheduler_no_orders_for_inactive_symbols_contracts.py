from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.run_plan import main as run_plan_main

SYMBOLS = ["au", "ag", "cu", "rb", "zn"]


def _write_topn_plan(
    tmp_path: Path,
    *,
    runtime_id: str,
    ticks: int = 30,
    active_top_n: int = 3,
    rank_emit_events: int = 1,
) -> Path:
    data_root = tmp_path / "data"
    plan_path = tmp_path / f"{runtime_id}.json"
    plan = {
        "schema_version": 1,
        "env": "dev",
        "adapters": {
            "market_data": {
                "mode": "simulated_v2",
                "params": {
                    "seed": 16,
                    "drift": 0.0001,
                    "vol": 0.01,
                    "start_prices": {s: 1000.0 + i for i, s in enumerate(SYMBOLS)},
                    "start_volumes": {s: 1000.0 + i * 100.0 for i, s in enumerate(SYMBOLS)},
                },
            }
        },
        "universe": {"symbols": SYMBOLS},
        "strategies": [
            {
                "name": "simple_strategy",
                "params": {},
                "symbols": SYMBOLS,
                "priority": 10,
                "weight": 1.0,
            }
        ],
        "instruments": {
            "roll_policy": {
                "mode": "fixed_contract",
                "contracts": {s: f"SHFE.{s}2406" for s in SYMBOLS},
            }
        },
        "runtime": {
            "ticks_live": ticks,
            "ticks_sandbox": 0,
            "default_quantity": 1.0,
            "active_top_n": active_top_n,
            "rank_window": 5,
            "rank_metric": "signal_strength",
            "rank_refresh_every": 1,
            "rank_emit_events": rank_emit_events,
        },
        "datastore": {
            "store_root": str(data_root / "store"),
            "artifacts_root": str(data_root / "artifacts"),
            "approved_dir": str(data_root / "artifacts" / "approved"),
            "decisions_dir": str(data_root / "artifacts" / "decisions"),
            "summaries_dir": str(data_root / "artifacts" / "summaries"),
            "manifests_dir": str(data_root / "artifacts" / "manifests"),
        },
        "promotion": {
            "min_events": 1,
            "min_success_rate_improvement": -1.0,
            "max_consecutive_failures": 99,
        },
        "router": {"mode": "priority", "tie_breaker": "priority"},
    }
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return plan_path


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_topn_scheduler_no_orders_for_inactive_symbols_contracts(tmp_path: Path) -> None:
    rid = "rt_topn_gate"
    plan_path = _write_topn_plan(tmp_path, runtime_id=rid)

    assert run_plan_main(["--config", str(plan_path), "--runtime-id", rid, "--clean"]) == 0

    store_dir = tmp_path / "data" / "store" / "live" / rid
    rank_events = _read_jsonl(store_dir / "rank_events.jsonl")
    assert rank_events
    active = {item["symbol"] for item in rank_events[0]["scores"]}
    assert len(active) == 3

    order_symbols = {ev["symbol"] for ev in _read_jsonl(store_dir / "order_events.jsonl")}
    fill_symbols = {ev["symbol"] for ev in _read_jsonl(store_dir / "fill_events.jsonl")}
    assert order_symbols
    assert order_symbols <= active
    assert fill_symbols <= active
    assert set(SYMBOLS) - active
    assert not ((set(SYMBOLS) - active) & (order_symbols | fill_symbols))
