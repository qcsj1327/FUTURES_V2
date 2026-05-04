from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from core.instruments.specs import InstrumentSpec


def write_specs_snapshot(
    *,
    runtime_id: str,
    specs: dict[str, InstrumentSpec],
    output_dir: Path = Path("data/artifacts/specs"),
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "runtime_id": runtime_id,
        "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "specs": {sym: asdict(spec) for sym, spec in sorted(specs.items())},
    }
    path = output_dir / f"specs_{runtime_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path

