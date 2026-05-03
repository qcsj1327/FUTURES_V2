from __future__ import annotations

import json
from pathlib import Path

from scripts.run_plan import main as run_plan_main


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_cost_fields_are_emitted_in_events_and_summary(tmp_path: Path) -> None:
    rid = "rt_cost_contract"
    source = _read_json(Path("plans/dev.cost_model.json"))
    data_root = tmp_path / "data"
    source["datastore"] = {
        "store_root": str(data_root / "store"),
        "artifacts_root": str(data_root / "artifacts"),
        "approved_dir": str(data_root / "artifacts" / "approved"),
        "decisions_dir": str(data_root / "artifacts" / "decisions"),
        "summaries_dir": str(data_root / "artifacts" / "summaries"),
        "manifests_dir": str(data_root / "artifacts" / "manifests"),
    }
    plan_path = tmp_path / "dev.cost_model.json"
    plan_path.write_text(json.dumps(source, ensure_ascii=False, indent=2), encoding="utf-8")

    assert run_plan_main(["--config", str(plan_path), "--runtime-id", rid, "--clean"]) == 0

    fills = _read_jsonl(data_root / "store" / "live" / rid / "fill_events.jsonl")
    assert fills
    cost_event = next(ev for ev in fills if isinstance(ev.get("cost_total"), (int, float)))
    for key in ("commission", "slippage", "cost_total", "notional", "multiplier", "tick_size"):
        assert isinstance(cost_event.get(key), (int, float))

    summary_path = data_root / "artifacts" / "summaries" / f"current_{rid}.json"
    summary_payload = _read_json(summary_path)
    summary = summary_payload.get("summary")
    assert isinstance(summary, dict)
    assert summary["commission_sum"] > 0
    assert summary["slippage_sum"] > 0
    assert summary["cost_total_sum"] == summary["commission_sum"] + summary["slippage_sum"]
    assert summary["notional_sum"] > 0
