from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.services.audit.contracts import (
    CANONICAL_AUDIT_SCOPES,
    AuditReport,
    ReadinessReport,
)

SENSITIVE_KEY_RE = re.compile(r"(token|password|secret|credential|env)", re.IGNORECASE)


def write_audit_report(
    report: AuditReport | Mapping[str, Any],
    *,
    artifacts_root: Path = Path("data/artifacts"),
) -> Path:
    payload = _payload(report)
    _validate_scoped_payload(payload)
    return _write_payload(
        payload,
        artifacts_root=artifacts_root,
        prefix="audit",
    )


def write_readiness_report(
    report: ReadinessReport,
    *,
    artifacts_root: Path = Path("data/artifacts"),
) -> Path:
    payload = _payload(report)
    _validate_scoped_payload(payload)
    if payload.get("artifact_type") != "readiness_report":
        raise ValueError("invalid readiness artifact_type")
    return _write_payload(
        payload,
        artifacts_root=artifacts_root,
        prefix="readiness",
    )


def _write_payload(
    payload: dict[str, Any],
    *,
    artifacts_root: Path,
    prefix: str,
) -> Path:
    scope = str(payload["datastore_scope"])
    runtime_id = str(payload["runtime_id"])
    generated_tag = _artifact_time_tag(str(payload["generated_at"]))
    out_dir = artifacts_root / scope / "audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{prefix}_{runtime_id}_{generated_tag}.json"
    safe_payload = _redact(payload)
    encoded = json.JSONEncoder(
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).encode(safe_payload)
    path.write_bytes((encoded + "\n").encode("utf-8"))
    return path


def _payload(value: AuditReport | ReadinessReport | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_dict"):
        data = value.to_dict()
    elif is_dataclass(value):
        data = value.__dict__
    else:
        raise TypeError("unsupported audit artifact payload")
    if not isinstance(data, dict):
        raise TypeError("audit artifact payload must be a dict")
    return data


def _validate_scoped_payload(payload: Mapping[str, Any]) -> None:
    for field in (
        "schema_version",
        "artifact_type",
        "runtime_id",
        "runtime_profile",
        "datastore_scope",
        "is_live",
        "generated_at",
    ):
        if payload.get(field) in (None, ""):
            raise ValueError(f"missing audit artifact field:{field}")
    runtime_profile = payload.get("runtime_profile")
    datastore_scope = payload.get("datastore_scope")
    if runtime_profile not in CANONICAL_AUDIT_SCOPES:
        raise ValueError(f"invalid runtime_profile:{runtime_profile}")
    if datastore_scope not in CANONICAL_AUDIT_SCOPES:
        raise ValueError(f"invalid datastore_scope:{datastore_scope}")
    if runtime_profile != datastore_scope:
        raise ValueError("runtime_profile/datastore_scope mismatch")
    if payload.get("is_live") is not (datastore_scope == "live"):
        raise ValueError("is_live mismatch")
    artifact_type = payload.get("artifact_type")
    if datastore_scope == "live":
        if artifact_type not in {"live_audit_observation", "live_audit_report", "readiness_report"}:
            raise ValueError("invalid live audit artifact_type")
    elif artifact_type not in {"runtime_diagnostics", "readiness_report"}:
        raise ValueError("invalid diagnostics artifact_type")


def _redact(value: Any, *, key: str | None = None) -> Any:
    if key is not None and SENSITIVE_KEY_RE.search(key):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {str(k): _redact(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return [_redact(item) for item in value]
    return value


def _artifact_time_tag(generated_at: str) -> str:
    try:
        parsed = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError:
        parsed = datetime.now(UTC)
    return parsed.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
