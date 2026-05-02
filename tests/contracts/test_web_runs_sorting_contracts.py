from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from scripts.run_plan import main as run_plan_main
from web.api.runs import list_runs


def test_web_runs_list_is_newest_first(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    # Force run_plan outputs into tmp_path so web/readmodel reads the right manifests
    artifacts_root = tmp_path / "data" / "artifacts"
    store_root = tmp_path / "data" / "store"

    plan = {
        "schema_version": 1,
        "env": "dev",
        "datastore": {
            "store_root": str(store_root),
            "artifacts_root": str(artifacts_root),
            "approved_dir": str(artifacts_root / "approved"),
            "decisions_dir": str(artifacts_root / "decisions"),
            "summaries_dir": str(artifacts_root / "summaries"),
            "manifests_dir": str(artifacts_root / "manifests"),
        },
        "universe": {"symbols": ["au"]},
        "strategies": [
            {
                "name": "simple_strategy",
                "params": {"force_decision": "HOLD"},
                "symbols": ["au"],
                "priority": 10,
                "weight": 1.0,
            }
        ],
        "runtime": {"ticks_live": 1, "ticks_sandbox": 1, "default_quantity": 1.0},
        "promotion": {
            "min_events": 1,
            "min_success_rate_improvement": -1.0,
            "max_consecutive_failures": 99,
        },
        "router": {"mode": "priority", "tie_breaker": "priority"},
    }

    cfg = tmp_path / "plan.json"
    cfg.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    assert run_plan_main(["--config", str(cfg), "--runtime-id", "rt_old", "--clean"]) == 0
    time.sleep(1.1)
    assert run_plan_main(["--config", str(cfg), "--runtime-id", "rt_new"]) == 0

    items = list_runs(artifacts_root=artifacts_root)
    ids = [x["runtime_id"] for x in items]

    assert "rt_new" in ids
    assert "rt_old" in ids
    assert ids.index("rt_new") < ids.index("rt_old")
