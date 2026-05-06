from __future__ import annotations

import json
from pathlib import Path

import pytest

from web.readmodel.dashboard import inspect_run
from web.readmodel.loader import load_run_from_manifest
from web.readmodel.repository import FileRepository


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _manifest(*, runtime_id: str, plan: dict[str, object]) -> dict[str, object]:
    return {
        "kind": "promotion_manifest",
        "runtime_id": runtime_id,
        "runtime_profile": "live",
        "datastore_scope": "live",
        "is_live": True,
        "created_at": "2026-05-08T00:00:00+00:00",
        "candidate_id": "cand",
        "status": "running",
        "plan": plan,
        "artifacts": {"current_summary": None},
    }


def test_inspect_run_rejects_manifest_plan_config(tmp_path: Path) -> None:
    rid = "rt_plan_config"
    _write_json(
        tmp_path / "artifacts" / "manifests" / f"manifest_{rid}_20260508T000000Z.json",
        _manifest(
            runtime_id=rid,
            plan={"path": "plan.json", "sha256": "sha", "config": {"runtime": {"mode": "live"}}},
        ),
    )

    report = inspect_run(
        runtime_id=rid,
        store_root=tmp_path / "store",
        artifacts_root=tmp_path / "artifacts",
    )

    assert report["fail_closed"] is True
    assert "plan.config" in report["fail_closed_reasons"][0]
    assert "config" not in report["plan"]


def test_loader_rejects_manifest_plan_config(tmp_path: Path) -> None:
    rid = "rt_plan_config"
    path = tmp_path / "artifacts" / "manifests" / f"manifest_{rid}_20260508T000000Z.json"
    _write_json(
        path,
        _manifest(
            runtime_id=rid,
            plan={"path": "plan.json", "sha256": "sha", "config": {"runtime": {"mode": "live"}}},
        ),
    )

    repo = FileRepository(artifacts_root=tmp_path / "artifacts")
    with pytest.raises(ValueError, match="plan.config"):
        load_run_from_manifest(repo, path)


def test_readmodel_returns_redacted_effective_config_summary(tmp_path: Path) -> None:
    rid = "rt_effective"
    _write_json(
        tmp_path / "artifacts" / "manifests" / f"manifest_{rid}_20260508T000000Z.json",
        _manifest(
            runtime_id=rid,
            plan={
                "path": "plan.json",
                "sha256": "sha",
                "effective_config_summary": {
                    "runtime": {"mode": "live"},
                    "universe": {"symbols": ["au"]},
                },
                "redaction_status": {"redacted": True},
            },
        ),
    )

    report = inspect_run(
        runtime_id=rid,
        store_root=tmp_path / "store",
        artifacts_root=tmp_path / "artifacts",
    )

    assert report.get("fail_closed") is not True
    assert "config" not in report["plan"]
    assert report["plan"]["effective_config_summary"]["runtime"]["mode"] == "live"
