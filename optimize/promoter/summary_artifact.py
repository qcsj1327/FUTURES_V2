from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def write_summary_artifact(
    *,
    runtime_id: str,
    role: str,  # "current" | "candidate"
    summary: Mapping[str, Any],
    output_dir: Path | None = None,
    filename: str | None = None,
    status: str | None = None,
) -> Path:
    out_dir = output_dir or Path("data/artifacts/summaries")
    out_dir.mkdir(parents=True, exist_ok=True)

    name = filename or f"{role}_{runtime_id}.json"
    path = out_dir / name

    payload: dict[str, Any] = {
        "kind": "promotion_summary",
        "schema_version": 1,
        "created_at": _utc_now_iso(),
        "runtime_id": runtime_id,
        "role": role,
        "summary": dict(summary),
    }
    if status is not None:
        payload["status"] = status

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
