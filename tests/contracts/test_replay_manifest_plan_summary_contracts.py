from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.replay_manifest import main as replay_main
from scripts.run_plan import main as run_plan_main


def test_replay_manifest_markdown_includes_plan_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    plan = {
        "schema_version": 1,
        "env": "dev",
        "universe": {"symbols": ["au", "ag"]},
        "strategies": [
            {
                "name": "simple_strategy",
                "params": {"force_decision": "HOLD"},
                "symbols": ["au", "ag"],
                "priority": 10,
                "weight": 0.7,
            },
            {
                "name": "simple_strategy_alt",
                "params": {"force_decision": "HOLD"},
                "symbols": ["au", "ag"],
                "priority": 20,
                "weight": 0.3,
            },
        ],
        "runtime": {"ticks_live": 2, "ticks_sandbox": 2, "default_quantity": 1.0},
        "promotion": {
            "min_events": 1,
            "min_success_rate_improvement": -1.0,
            "max_consecutive_failures": 99,
        },
        "router": {"mode": "netting", "tie_breaker": "priority"},
    }

    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    rid = "rt_md"
    rc = run_plan_main(["--config", str(plan_path), "--runtime-id", rid, "--clean"])
    assert rc == 0

    mdir = tmp_path / "data" / "artifacts" / "manifests"
    manifests = list(mdir.glob(f"manifest_{rid}_*.json"))
    assert len(manifests) >= 1

    out_md = tmp_path / "report.md"
    rc2 = replay_main([str(manifests[0]), "--format", "md", "--output", str(out_md)])
    assert rc2 == 0

    text = out_md.read_text(encoding="utf-8")
    assert "## Plan summary" in text
    assert "plan_sha256" in text
    assert "router_mode" in text
    assert "universe_symbols" in text
    assert "strategy_names" in text
