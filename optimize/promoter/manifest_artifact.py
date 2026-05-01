from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def write_promotion_manifest(
    *,
    runtime_id: str,
    candidate_id: str,
    candidate_config: Mapping[str, Any],
    thresholds: Mapping[str, Any],
    current_summary_path: Path | None,
    candidate_summary_path: Path | None,
    decision_path: Path | None,
    approved_path: Path | None,
    plan: Mapping[str, Any] | None = None,
    plan_path: str | None = None,
    plan_sha256: str | None = None,
    output_dir: Path | None = None,
    filename: str | None = None,
) -> Path:
    out_dir = output_dir or Path("data/artifacts/manifests")
    out_dir.mkdir(parents=True, exist_ok=True)

    name = filename or f"manifest_{runtime_id}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    path = out_dir / name

    payload: dict[str, Any] = {
        "kind": "promotion_manifest",
        "schema_version": 1,
        "created_at": _utc_now_iso(),
        "runtime_id": runtime_id,
        "candidate_id": candidate_id,
        "candidate_config": dict(candidate_config),
        "thresholds": dict(thresholds),
        "plan": {
            "path": plan_path,
            "sha256": plan_sha256,
            "config": dict(plan) if plan is not None else None,
        },
        "artifacts": {
            "current_summary": str(current_summary_path) if current_summary_path else None,
            "candidate_summary": str(candidate_summary_path) if candidate_summary_path else None,
            "decision": str(decision_path) if decision_path else None,
            "approved": str(approved_path) if approved_path else None,
        },
    }

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
