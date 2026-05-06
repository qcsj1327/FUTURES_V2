from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from web.readmodel.models import RunListItem, RunReadModel
from web.readmodel.repository import FileRepository

OPTIONAL_ARTIFACT_WARNING_CODES = {
    "missing_candidate_summary",
    "missing_decision",
    "missing_approved",
    "missing_strategy_switch_approved",
    "missing_strategy_switch_rejected",
}

CANONICAL_RUNTIME_PROFILES = {"local", "dryrun", "live"}
CANONICAL_RUNTIME_IDS = {"rt_local", "rt_dryrun", "rt_live"}


def _manifest_ts(path_str: str) -> str:
    name = Path(path_str).name
    m = re.match(r"^manifest_.*_([0-9]{8}T[0-9]{6}Z)\.json$", name)
    return m.group(1) if m else ""


def _as_dict(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _as_list_str(v: Any) -> list[str]:
    if not isinstance(v, list):
        return []
    return [x for x in v if isinstance(x, str)]


def _plan_config_from_manifest(m: dict[str, Any]) -> dict[str, Any]:
    plan = _as_dict(m.get("plan"))
    if isinstance(plan.get("config"), dict):
        raise ValueError("invalid_manifest_schema:plan.config")
    cfg = _as_dict(plan.get("effective_config_summary"))
    if not cfg:
        raise ValueError("invalid_manifest_schema:missing_effective_config_summary")
    runtime_profile = m.get("runtime_profile")
    datastore_scope = m.get("datastore_scope")
    if runtime_profile not in CANONICAL_RUNTIME_PROFILES:
        raise ValueError(f"invalid_manifest_schema:runtime_profile:{runtime_profile}")
    if datastore_scope not in CANONICAL_RUNTIME_PROFILES:
        raise ValueError(f"invalid_manifest_schema:datastore_scope:{datastore_scope}")
    if runtime_profile != datastore_scope:
        raise ValueError("invalid_manifest_schema:profile_scope_mismatch")
    runtime = dict(_as_dict(cfg.get("runtime")))
    if runtime.get("mode") != runtime_profile:
        raise ValueError("invalid_manifest_schema:runtime_mode_mismatch")
    cfg["runtime"] = runtime
    return cfg


def _load_artifact_payload(
    repo: FileRepository,
    path_str: Any,
    *,
    required: bool = True,
    warnings: list[str] | None = None,
    name: str = "artifact",
) -> dict[str, Any]:
    if not isinstance(path_str, str) or not path_str.strip():
        if warnings is not None:
            warnings.append(f"missing_{name}")
            return {}
        if required:
            raise ValueError("artifact path must be a non-empty string")
        return {}
    p = Path(path_str)
    if not p.exists():
        if warnings is not None:
            warnings.append(f"missing_{name}")
            warnings.append(f"missing_{name}_file:{p}")
            return {}
        raise FileNotFoundError(f"artifact not found: {p}")
    return repo.read_json(p)


def load_run_from_manifest(repo: FileRepository, manifest_path: Path) -> RunReadModel:
    m = repo.read_json(manifest_path)
    if str(m.get("kind")) != "promotion_manifest":
        raise ValueError("not a promotion_manifest")

    runtime_id = str(m.get("runtime_id"))
    created_at = m.get("created_at")
    candidate_id = m.get("candidate_id")

    artifacts = _as_dict(m.get("artifacts"))
    thresholds = _as_dict(m.get("thresholds"))
    warnings: list[str] = []
    optional_warnings: list[str] = []

    cur_payload = _load_artifact_payload(
        repo,
        artifacts.get("current_summary"),
        required=True,
        warnings=warnings,
        name="current_summary",
    )
    cand_payload = _load_artifact_payload(
        repo,
        artifacts.get("candidate_summary"),
        required=False,
        warnings=warnings,
        name="candidate_summary",
    )
    dec_payload = _load_artifact_payload(
        repo,
        artifacts.get("decision"),
        required=False,
        warnings=warnings,
        name="decision",
    )
    if dec_payload is None:
        dec_payload = {}

    approved_payload: dict[str, Any] | None = None
    approved_ref = artifacts.get("approved")
    if isinstance(approved_ref, str) and approved_ref:
        p = Path(approved_ref)
        if p.exists():
            approved_payload = repo.read_json(p)
        else:
            warnings.append("missing_approved")
    else:
        warnings.append("missing_approved")
    optional_warnings = [
        code
        for code in warnings
        if code in OPTIONAL_ARTIFACT_WARNING_CODES
        or code.startswith(tuple(f"{x}_file:" for x in OPTIONAL_ARTIFACT_WARNING_CODES))
    ]
    warnings = [code for code in warnings if code not in optional_warnings]

    # plan metadata
    plan = _as_dict(m.get("plan"))
    plan_path = plan.get("path") if isinstance(plan.get("path"), str) else None
    plan_sha256 = plan.get("sha256") if isinstance(plan.get("sha256"), str) else None
    plan_config = _plan_config_from_manifest(m)

    return RunReadModel(
        runtime_id=runtime_id,
        created_at=str(created_at) if created_at is not None else None,
        candidate_id=str(candidate_id) if candidate_id is not None else None,
        manifest_path=str(manifest_path),
        plan_path=plan_path,
        plan_sha256=plan_sha256,
        plan_config=plan_config,
        current_summary=cur_payload,
        candidate_summary=cand_payload,
        decision=dec_payload,
        approved=approved_payload,
        thresholds=thresholds,
        warnings=warnings,
        optional_warnings=optional_warnings,
    )


def list_runs(repo: FileRepository) -> list[RunListItem]:
    latest_by_runtime: dict[str, RunListItem] = {}
    for p in repo.list_manifest_paths():
        try:
            m = repo.read_json(p)
        except Exception:
            continue
        if str(m.get("kind")) != "promotion_manifest":
            continue

        runtime_id = str(m.get("runtime_id", ""))
        if runtime_id not in CANONICAL_RUNTIME_IDS:
            continue
        created_at = str(m.get("created_at")) if m.get("created_at") is not None else None

        plan = _as_dict(m.get("plan"))
        plan_sha256 = plan.get("sha256") if isinstance(plan.get("sha256"), str) else None
        cfg = _plan_config_from_manifest(m)
        runtime = _as_dict(cfg.get("runtime"))
        if runtime.get("mode") not in CANONICAL_RUNTIME_PROFILES:
            continue
        router = _as_dict(cfg.get("router"))
        router_mode = router.get("mode") if isinstance(router.get("mode"), str) else None
        universe = _as_dict(cfg.get("universe"))
        universe_symbols = _as_list_str(universe.get("symbols"))
        strategies_raw = cfg.get("strategies")
        strategy_names: list[str] = []
        if isinstance(strategies_raw, list):
            for s in strategies_raw:
                if isinstance(s, dict) and isinstance(s.get("name"), str):
                    strategy_names.append(s["name"])

        approved: bool | None = None
        artifacts = _as_dict(m.get("artifacts"))
        if isinstance(artifacts.get("decision"), str) and Path(artifacts["decision"]).exists():
            dec_payload = repo.read_json(Path(artifacts["decision"]))
            decision_obj = _as_dict(dec_payload.get("decision"))
            if isinstance(decision_obj.get("approved"), bool):
                approved = decision_obj["approved"]

        item = RunListItem(
            runtime_id=runtime_id,
            created_at=created_at,
            approved=approved,
            router_mode=router_mode,
            universe_symbols=universe_symbols,
            strategy_names=strategy_names,
            plan_sha256=plan_sha256,
            manifest_path=str(p),
        )
        old = latest_by_runtime.get(runtime_id)
        if old is None or _run_sort_key(item) > _run_sort_key(old):
            latest_by_runtime[runtime_id] = item
    # newest first by created_at then manifest filename (stable)
    items = list(latest_by_runtime.values())
    items.sort(
        key=_run_sort_key,
        reverse=True,
    )
    return items


def _run_sort_key(item: RunListItem) -> tuple[str, str, str]:
    return (
        _manifest_ts(item.manifest_path),
        item.runtime_id,
        Path(item.manifest_path).name,
    )
