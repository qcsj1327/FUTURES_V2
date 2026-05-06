from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from core.instruments.specs import InstrumentSpec


def validate_specs_snapshot_scope(
    *,
    path: Path,
    expected_runtime_profile: str,
    expected_datastore_scope: str,
) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid specs snapshot: {path}")
    if payload.get("runtime_profile") != expected_runtime_profile:
        raise ValueError("spec artifact runtime_profile mismatch")
    if payload.get("datastore_scope") != expected_datastore_scope:
        raise ValueError("spec artifact datastore_scope mismatch")
    if payload.get("is_live") is not (expected_datastore_scope == "live"):
        raise ValueError("spec artifact is_live mismatch")
    return payload


def write_specs_snapshot(
    *,
    runtime_id: str,
    runtime_profile: str,
    datastore_scope: str,
    specs: dict[str, InstrumentSpec],
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1",
        "artifact_type": "instrument_specs",
        "runtime_id": runtime_id,
        "runtime_profile": runtime_profile,
        "datastore_scope": datastore_scope,
        "is_live": datastore_scope == "live",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "specs": {sym: asdict(spec) for sym, spec in sorted(specs.items())},
    }
    path = output_dir / f"specs_{runtime_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
