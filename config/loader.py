from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from config.defaults import default_plan
from config.models import RunPlan


def load_plan(path: Path | None, *, runtime_id: str) -> RunPlan:
    # For now: file optional, fallback to code defaults.
    # (You can later add merge/validate/schema migration here.)
    if path is None:
        return default_plan(runtime_id=runtime_id)

    raw = json.loads(path.read_text(encoding="utf-8"))
    # Minimal strictness: require schema_version and basic keys.
    if raw.get("schema_version") != 1:
        raise ValueError("unsupported schema_version")

    # Re-hydrate by delegating to defaults then overriding simple fields.
    plan = default_plan(runtime_id=runtime_id)

    # Shallow override for now; avoid surprise deep merges.
    # Keep this loader simple and deterministic.
    if "env" in raw:
        plan = RunPlan(**{**asdict(plan), "env": raw["env"]})
    return plan
