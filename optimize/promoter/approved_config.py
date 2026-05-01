from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def write_approved_config(
    *,
    approved: bool,
    candidate_id: str,
    candidate_config: Mapping[str, Any],
    decision_deltas: Mapping[str, Any],
    thresholds: Mapping[str, Any],
    current_metrics: Mapping[str, Any] | None = None,
    candidate_metrics: Mapping[str, Any] | None = None,
    output_dir: Path | None = None,
    filename: str | None = None,
) -> Path | None:
    """
    Write an approved config artifact (JSON) when approved=True.
    Returns the written file path, otherwise None.
    """
    if not approved:
        return None

    out_dir = output_dir or Path("data/artifacts/approved")
    out_dir.mkdir(parents=True, exist_ok=True)

    name = filename or f"approved_{candidate_id}.json"
    path = out_dir / name

    payload: dict[str, Any] = {
        "kind": "approved_config",
        "schema_version": 1,
        "created_at": _utc_now_iso(),
        "candidate_id": candidate_id,
        "candidate_config": dict(candidate_config),
        "decision_deltas": dict(decision_deltas),
        "thresholds": dict(thresholds),
    }

    if current_metrics is not None:
        payload["current_metrics"] = dict(current_metrics)
    if candidate_metrics is not None:
        payload["candidate_metrics"] = dict(candidate_metrics)

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
