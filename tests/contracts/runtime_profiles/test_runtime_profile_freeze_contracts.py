from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from config.loader import load_plan

RUNTIME_PROFILES = {"local", "dryrun", "live"}


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _forbidden_legacy_tokens() -> list[str]:
    # Keep these split so this guard does not itself become a grep false positive.
    return [
        "simulated" + "_" + "v2",
        "live" + "_" + "file",
        "tqkq" + "_" + "sim",
        "tqkq" + "_" + "live",
        "tqkq" + "_" + "dryrun",
        "tqkq" + "_" + "live" + "_" + "submit",
        "sand" + "box",
    ]


def test_only_three_canonical_plan_profiles_remain() -> None:
    plan_names = sorted(path.name for path in Path("plans").glob("*.json"))

    assert plan_names == [
        "dev.dryrun.json",
        "dev.live.json",
        "dev.local.json",
        "prices.json",
    ]


def test_canonical_plans_use_frozen_runtime_profiles() -> None:
    expected = {
        "dev.local.json": ("local", "local_file", "simulated"),
        "dev.dryrun.json": ("dryrun", "tqkq", "tqkq"),
        "dev.live.json": ("live", "tqkq", "tqkq"),
    }

    for filename, (runtime_mode, market_mode, broker_mode) in expected.items():
        plan = load_plan(Path("plans") / filename, runtime_id=f"rt_{runtime_mode}")
        assert plan.runtime.mode == runtime_mode
        assert plan.adapters.market_data.mode == market_mode
        assert plan.adapters.broker.mode == broker_mode


def test_dev_script_only_accepts_frozen_profiles() -> None:
    text = Path("scripts/dev_up.sh").read_text(encoding="utf-8")

    assert "plans/dev.local.json" in text
    assert "plans/dev.dryrun.json" in text
    assert "plans/dev.live.json" in text
    for token in _forbidden_legacy_tokens():
        assert token not in text


def test_tests_do_not_depend_on_legacy_runtime_names() -> None:
    offenders: list[str] = []
    for path in sorted(Path("tests").rglob("*.py")):
        if path == Path(__file__):
            continue
        text = path.read_text(encoding="utf-8")
        for token in _forbidden_legacy_tokens():
            if token in text:
                offenders.append(f"{path}:{token}")

    assert offenders == []


def test_current_runtime_code_does_not_reference_legacy_runtime_names() -> None:
    offenders: list[str] = []
    for root in ("app", "core", "adapters", "optimize", "web", "config"):
        for path in sorted(Path(root).rglob("*")):
            if path.suffix not in {".py", ".sh", ".json"}:
                continue
            text = path.read_text(encoding="utf-8")
            for token in _forbidden_legacy_tokens():
                if token in text:
                    offenders.append(f"{path}:{token}")

    assert offenders == []


def test_old_runtime_modes_are_rejected_not_mapped(tmp_path: Path) -> None:
    for mode in _forbidden_legacy_tokens():
        if mode == "sand" + "box":
            continue
        plan = {
            "schema_version": 1,
            "runtime": {"mode": mode},
        }
        path = tmp_path / f"{mode}.json"
        path.write_text(json.dumps(plan), encoding="utf-8")

        with pytest.raises(ValueError, match="invalid runtime.mode"):
            load_plan(path, runtime_id="rt_legacy_reject")


def test_clean_runtime_paths_only_removes_profile_scopes(tmp_path: Path) -> None:
    from app.orchestration.run_cleanup import clean_runtime_paths

    store_root = tmp_path / "store"
    artifacts_root = tmp_path / "artifacts"
    for scope in RUNTIME_PROFILES:
        target = store_root / scope / "rt_freeze"
        target.mkdir(parents=True)
        (target / "fill_events.jsonl").write_text("{}", encoding="utf-8")
    untouched = store_root / "archive" / "rt_freeze"
    untouched.mkdir(parents=True)
    (untouched / "fill_events.jsonl").write_text("{}", encoding="utf-8")

    clean_runtime_paths(
        runtime_id="rt_freeze",
        store_root=store_root,
        artifacts_root=artifacts_root,
    )

    for scope in RUNTIME_PROFILES:
        assert not (store_root / scope / "rt_freeze").exists()
    assert untouched.exists()
