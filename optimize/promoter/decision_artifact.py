from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def write_promotion_decision(
    *,
    runtime_id: str,
    decision: Mapping[str, Any],
    thresholds: Mapping[str, Any],
    current_metrics: Mapping[str, Any] | None = None,
    candidate_metrics: Mapping[str, Any] | None = None,
    output_dir: Path | None = None,
    filename: str | None = None,
) -> Path:
    out_dir = output_dir or Path("data/artifacts/decisions")
    out_dir.mkdir(parents=True, exist_ok=True)

    name = filename or f"decision_{runtime_id}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    path = out_dir / name

    payload: dict[str, Any] = {
        "kind": "promotion_decision",
        "schema_version": 1,
        "created_at": _utc_now_iso(),
        "runtime_id": runtime_id,
        "decision": dict(decision),
        "thresholds": dict(thresholds),
    }
    if current_metrics is not None:
        payload["current_metrics"] = dict(current_metrics)
    if candidate_metrics is not None:
        payload["candidate_metrics"] = dict(candidate_metrics)

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
