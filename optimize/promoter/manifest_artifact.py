from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

SENSITIVE_KEY_PARTS = (
    "token",
    "password",
    "passwd",
    "secret",
    "credential",
    "api_key",
    "apikey",
    "account",
    "env",
)
PATH_KEY_PARTS = ("path", "file", "dir", "root")


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def manifest_safe_path(value: str | Path | None) -> str | None:
    if value is None:
        return None
    raw = str(value)
    if not raw:
        return raw
    path = Path(raw)
    if path.is_absolute():
        return f"<redacted>/{path.name}"
    return raw


def redaction_status() -> dict[str, Any]:
    return {
        "redacted": True,
        "rules": [
            "sensitive_keys",
            "private_absolute_paths",
            "full_plan_config_omitted",
        ],
    }


def redact_manifest_value(value: Any, *, key: str | None = None) -> Any:
    key_l = (key or "").lower()
    if _is_sensitive_key(key_l):
        return _redacted_secret(value)
    if isinstance(value, Mapping):
        return {
            str(k): redact_manifest_value(v, key=str(k))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact_manifest_value(item) for item in value]
    if isinstance(value, tuple):
        return [redact_manifest_value(item) for item in value]
    if isinstance(value, Path):
        return manifest_safe_path(value)
    if isinstance(value, str) and _is_path_key(key_l):
        return manifest_safe_path(value)
    return value


def redacted_effective_plan_summary(plan: Mapping[str, Any] | None) -> dict[str, Any]:
    if plan is None:
        return {}

    runtime = _mapping(plan.get("runtime"))
    datastore = _mapping(plan.get("datastore"))
    universe = _mapping(plan.get("universe"))
    instruments = _mapping(plan.get("instruments"))
    router = _mapping(plan.get("router"))
    promotion = _mapping(plan.get("promotion"))
    strategy_switch = _mapping(plan.get("strategy_switch"))
    adapters = _mapping(plan.get("adapters"))

    summary: dict[str, Any] = {
        "runtime_profile": runtime.get("mode"),
        "datastore_scope": runtime.get("mode"),
        "runtime": _select(
            runtime,
            {
                "mode",
                "runtime_id",
                "active_top_n",
                "rank_window",
                "rank_metric",
                "rank_refresh_every",
                "rank_emit_events",
                "default_quantity",
            },
        ),
        "datastore": {
            "store_root": manifest_safe_path(_str_or_none(datastore.get("store_root"))),
            "artifacts_root": manifest_safe_path(_str_or_none(datastore.get("artifacts_root"))),
        },
        "universe": {
            "symbols": _list_str(universe.get("symbols")),
        },
        "instruments": _instrument_summary(instruments),
        "router": _select(router, {"mode", "tie_breaker"}),
        "strategies": _strategy_summaries(plan.get("strategies")),
        "promotion": _select(
            promotion,
            {
                "write_summary",
                "write_decision",
                "write_manifest",
                "write_approved",
                "min_events",
                "max_consecutive_failures",
            },
        ),
        "strategy_switch": _select(
            strategy_switch,
            {
                "enabled_by_symbol",
                "approval_required",
                "min_score",
                "max_enabled_strategies_per_symbol",
            },
        ),
        "adapters": _adapter_summary(adapters),
    }
    return cast(dict[str, Any], redact_manifest_value(summary))


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
    strategy_switch_proposal_path: Path | None = None,
    strategy_switch_approved_path: Path | None = None,
    plan: Mapping[str, Any] | None = None,
    plan_path: str | None = None,
    plan_sha256: str | None = None,
    output_dir: Path | None = None,
    filename: str | None = None,
    run_mode: str = "batch",
    runtime_profile: str | None = None,
    datastore_scope: str | None = None,
    status: str | None = None,
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
        "run_mode": run_mode,
        "runtime_profile": runtime_profile,
        "datastore_scope": datastore_scope,
        "candidate_id": candidate_id,
        "candidate_config": dict(candidate_config),
        "thresholds": dict(thresholds),
        "plan": {
            "path": manifest_safe_path(plan_path),
            "sha256": plan_sha256,
            "effective_config_summary": redacted_effective_plan_summary(plan),
            "redaction_status": redaction_status(),
        },
        "artifacts": {
            "current_summary": str(current_summary_path) if current_summary_path else None,
            "candidate_summary": str(candidate_summary_path) if candidate_summary_path else None,
            "decision": str(decision_path) if decision_path else None,
            "approved": str(approved_path) if approved_path else None,
            "strategy_switch_proposal": (
                str(strategy_switch_proposal_path) if strategy_switch_proposal_path else None
            ),
            "strategy_switch_approved": (
                str(strategy_switch_approved_path) if strategy_switch_approved_path else None
            ),
        },
    }
    if status is not None:
        payload["status"] = status

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _is_sensitive_key(key: str) -> bool:
    return any(part in key for part in SENSITIVE_KEY_PARTS)


def _is_path_key(key: str) -> bool:
    return any(part in key for part in PATH_KEY_PARTS)


def _redacted_secret(value: Any) -> dict[str, Any]:
    if value is None:
        return {"present": False}
    text = str(value)
    return {
        "present": bool(text),
        "length": len(text),
        "sha256_prefix": hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
        if text
        else None,
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _select(source: Mapping[str, Any], keys: set[str]) -> dict[str, Any]:
    return {
        key: redact_manifest_value(value, key=key)
        for key, value in source.items()
        if key in keys
    }


def _list_str(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _str_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _instrument_summary(instruments: Mapping[str, Any]) -> dict[str, Any]:
    roll = _mapping(instruments.get("roll_policy"))
    return {
        "trading_sessions": _trading_sessions_summary(instruments.get("trading_sessions")),
        "roll_policy": {
            "mode": roll.get("mode"),
            "contracts": _str_mapping(roll.get("contracts")),
            "resolve_from_market_data": roll.get("resolve_from_market_data"),
            "close_on_roll": roll.get("close_on_roll"),
            "cooldown_ticks": roll.get("cooldown_ticks"),
            "main_contract_schedule": _list_mapping(roll.get("main_contract_schedule")),
        },
        "spec_source": instruments.get("spec_source"),
    }


def _trading_sessions_summary(value: Any) -> dict[str, list[dict[str, str]]]:
    if not isinstance(value, Mapping):
        return {}
    out: dict[str, list[dict[str, str]]] = {}
    for symbol, sessions in value.items():
        if not isinstance(symbol, str) or not isinstance(sessions, list):
            continue
        parsed: list[dict[str, str]] = []
        for session in sessions:
            item = _mapping(session)
            start = _str_or_none(item.get("start"))
            end = _str_or_none(item.get("end"))
            if start and end:
                parsed.append({"start": start, "end": end})
        if parsed:
            out[symbol] = parsed
    return out


def _str_mapping(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {
        key: val
        for key, val in value.items()
        if isinstance(key, str) and isinstance(val, str)
    }


def _list_mapping(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, Mapping):
        return {}
    out: dict[str, list[str]] = {}
    for key, val in value.items():
        if not isinstance(key, str) or not isinstance(val, list):
            continue
        parsed = [item for item in val if isinstance(item, str)]
        if parsed:
            out[key] = parsed
    return out


def _strategy_summaries(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        out.append(
            _select(
                item,
                {
                    "name",
                    "symbols",
                    "priority",
                    "weight",
                },
            )
        )
    return out


def _adapter_summary(adapters: Mapping[str, Any]) -> dict[str, Any]:
    market_data = _mapping(adapters.get("market_data"))
    broker = _mapping(adapters.get("broker"))
    market_params = _mapping(market_data.get("params"))
    broker_params = _mapping(broker.get("params"))
    return {
        "market_data": {
            "mode": market_data.get("mode"),
            "prices_path": manifest_safe_path(_str_or_none(market_data.get("prices_path"))),
            "tq_symbols": redact_manifest_value(market_params.get("tq_symbols")),
        },
        "broker": {
            "mode": broker.get("mode"),
            "submit_mode": broker_params.get("submit_mode"),
            "confirm_live": broker_params.get("confirm_live"),
            "confirm_live_token": redact_manifest_value(
                broker_params.get("confirm_live_token"),
                key="confirm_live_token",
            ),
            "order_id_prefix": broker_params.get("order_id_prefix"),
            "no_fill": broker_params.get("no_fill"),
        },
    }
