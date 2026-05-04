from __future__ import annotations

import json
from pathlib import Path

from tools.inspect_run import inspect_run


def test_inspect_run_reports_missing_artifact_warnings(tmp_path: Path) -> None:
    rid = "rt_inspect_warn"
    artifacts_root = tmp_path / "artifacts"
    manifests_dir = artifacts_root / "manifests"
    manifests_dir.mkdir(parents=True)
    manifest_path = manifests_dir / "manifest_rt_inspect_warn_20260101T000000Z.json"
    manifest_path.write_text(
        json.dumps(
            {
                "kind": "promotion_manifest",
                "runtime_id": rid,
                "created_at": "2026-01-01T00:00:00Z",
                "candidate_id": f"cand_{rid}",
                "plan": {"path": "plan.json", "sha256": "x", "config": {}},
                "artifacts": {
                    "current_summary": str(artifacts_root / "missing_current.json"),
                    "candidate_summary": str(artifacts_root / "missing_candidate.json"),
                    "decision": str(artifacts_root / "missing_decision.json"),
                    "approved": str(artifacts_root / "missing_approved.json"),
                },
            }
        ),
        encoding="utf-8",
    )

    report = inspect_run(
        runtime_id=rid,
        store_root=tmp_path / "store",
        artifacts_root=artifacts_root,
    )

    warnings = set(report["warnings"])
    assert {
        "missing_current_summary",
        "missing_candidate_summary",
        "missing_decision",
        "missing_approved",
    } <= warnings
    assert any(w.startswith("missing_current_summary_file:") for w in warnings)
    assert report["summaries"] == {"current": None, "candidate": None}
    assert report["decision"] is None
    assert report["approved"] is None
