from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

CANONICAL_AUDIT_SCOPES = {"local", "dryrun", "live"}


def load_audit_projection(
    *,
    runtime_id: str,
    scope: str,
    artifacts_root: Path = Path("data/artifacts"),
) -> dict[str, Any]:
    if scope not in CANONICAL_AUDIT_SCOPES:
        return _empty(scope=scope, reason="invalid_scope")
    audit_dir = artifacts_root / scope / "audit"
    audit = _latest_scoped_artifact(
        audit_dir,
        prefix="audit",
        runtime_id=runtime_id,
        expected_scope=scope,
    )
    readiness = _latest_scoped_artifact(
        audit_dir,
        prefix="readiness",
        runtime_id=runtime_id,
        expected_scope=scope,
    )
    alerts = _audit_alerts(audit)
    return {
        "scope": scope,
        "runtime_id": runtime_id,
        "source": "audit_artifact",
        "is_source_of_truth": False,
        "mutation_allowed": False,
        "diagnostic_only": scope != "live",
        "audit": audit,
        "readiness": readiness,
        "alerts": alerts,
    }


def _empty(*, scope: str, reason: str) -> dict[str, Any]:
    return {
        "scope": scope,
        "runtime_id": None,
        "source": "audit_artifact",
        "is_source_of_truth": False,
        "mutation_allowed": False,
        "diagnostic_only": True,
        "audit": None,
        "readiness": None,
        "alerts": [],
        "empty_reason": reason,
    }


def _latest_scoped_artifact(
    audit_dir: Path,
    *,
    prefix: str,
    runtime_id: str,
    expected_scope: str,
) -> dict[str, Any] | None:
    if not audit_dir.exists():
        return None
    for path in sorted(audit_dir.glob(f"{prefix}_{runtime_id}_*.json"), reverse=True):
        payload = _read_json(path)
        if payload is None:
            continue
        if _valid_scope(payload, expected_scope=expected_scope):
            return payload
    return None


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _valid_scope(payload: Mapping[str, Any], *, expected_scope: str) -> bool:
    if expected_scope not in CANONICAL_AUDIT_SCOPES:
        return False
    if payload.get("runtime_profile") != expected_scope:
        return False
    if payload.get("datastore_scope") != expected_scope:
        return False
    if payload.get("is_live") is not (expected_scope == "live"):
        return False
    if payload.get("is_source_of_truth") is not False:
        return False
    if payload.get("mutation_allowed") is not False:
        return False
    return True


def _audit_alerts(audit: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(audit, Mapping):
        return []
    raw_alerts = audit.get("alerts")
    if not isinstance(raw_alerts, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw_alerts:
        if not isinstance(item, Mapping):
            continue
        out.append(
            {
                "code": item.get("code"),
                "level": _level(item.get("severity")),
                "message": item.get("message"),
                "source": "audit_artifact",
                "suggested_action": item.get("suggested_action"),
                "is_source_of_truth": False,
                "mutation_allowed": False,
                "diagnostic_only": item.get("diagnostic_only") is True,
            }
        )
    return out


def _level(severity: Any) -> str:
    if severity == "critical":
        return "error"
    if severity == "warning":
        return "warning"
    return "info"
