from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CANONICAL_SCOPES = {"local", "dryrun", "live"}
ENVELOPE_ONLY_FIELDS = {
    "runtime_profile",
    "datastore_scope",
    "execution_env",
    "broker_profile",
    "submit_mode",
    "is_live",
    "is_simulated_execution",
    "source",
}
REQUIRED_ENVELOPE_FIELDS = {
    "schema_version",
    "event_id",
    "event_type",
    "runtime_id",
    "runtime_profile",
    "datastore_scope",
    "execution_env",
    "broker_profile",
    "submit_mode",
    "is_live",
    "is_simulated_execution",
    "generated_at",
    "source",
    "payload_type",
}


@dataclass(frozen=True)
class ValidatedRows:
    rows: list[dict[str, Any]]
    invalid_count: int
    invalid_reasons: dict[str, int]


def flatten_valid_event_row(
    row: Mapping[str, Any],
    *,
    expected_scope: str,
) -> tuple[dict[str, Any] | None, str | None]:
    if expected_scope not in CANONICAL_SCOPES:
        return None, f"invalid_requested_scope:{expected_scope}"
    envelope = row.get("envelope")
    payload = row.get("payload")
    if not isinstance(envelope, Mapping):
        return None, "missing_envelope"
    if not isinstance(payload, Mapping):
        return None, "missing_payload"

    for field in sorted(REQUIRED_ENVELOPE_FIELDS):
        if envelope.get(field) in (None, ""):
            return None, f"missing_envelope_field:{field}"

    runtime_profile = envelope.get("runtime_profile")
    datastore_scope = envelope.get("datastore_scope")
    if runtime_profile not in CANONICAL_SCOPES:
        return None, f"invalid_runtime_profile:{runtime_profile}"
    if datastore_scope not in CANONICAL_SCOPES:
        return None, f"invalid_datastore_scope:{datastore_scope}"
    if runtime_profile != expected_scope:
        return None, f"runtime_profile_mismatch:{runtime_profile}:{expected_scope}"
    if datastore_scope != expected_scope:
        return None, f"datastore_scope_mismatch:{datastore_scope}:{expected_scope}"

    is_live = envelope.get("is_live")
    if not isinstance(is_live, bool):
        return None, "invalid_is_live"
    if is_live is not (expected_scope == "live"):
        return None, f"is_live_mismatch:{expected_scope}"
    if not isinstance(envelope.get("is_simulated_execution"), bool):
        return None, "invalid_is_simulated_execution"

    bad_payload_fields = sorted(set(payload).intersection(ENVELOPE_ONLY_FIELDS))
    if bad_payload_fields:
        return None, "payload_contains_envelope_fields:" + ",".join(bad_payload_fields)

    return {**dict(payload), **dict(envelope)}, None


def read_valid_event_rows(
    path: Path,
    *,
    expected_scope: str,
    tail: int,
) -> ValidatedRows:
    if not path.exists():
        return ValidatedRows(rows=[], invalid_count=0, invalid_reasons={})
    lines = path.read_text(encoding="utf-8").splitlines()
    selected = lines[-tail:] if tail > 0 else lines
    rows: list[dict[str, Any]] = []
    reasons: Counter[str] = Counter()
    for line in selected:
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            reasons["invalid_json"] += 1
            continue
        if not isinstance(raw, Mapping):
            reasons["invalid_row_type"] += 1
            continue
        flat, reason = flatten_valid_event_row(raw, expected_scope=expected_scope)
        if flat is None:
            reasons[reason or "invalid_event"] += 1
            continue
        rows.append(flat)
    return ValidatedRows(
        rows=rows,
        invalid_count=sum(reasons.values()),
        invalid_reasons=dict(sorted(reasons.items())),
    )
