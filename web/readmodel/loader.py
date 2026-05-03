from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from web.readmodel.models import RunListItem, RunReadModel
from web.readmodel.repository import FileRepository


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


def _load_artifact_payload(
    repo: FileRepository,
    path_str: Any,
    *,
    required: bool = True,
    warnings: list[str] | None = None,
    name: str = "artifact",
) -> dict[str, Any]:
    if not isinstance(path_str, str) or not path_str.strip():
        if required:
            if warnings is not None:
                warnings.append(f"missing_{name}_path")
                return {}
            raise ValueError("artifact path must be a non-empty string")
        return {}
    p = Path(path_str)
    if not p.exists():
        if warnings is not None:
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
            warnings.append(f"missing_approved_file:{p}")

    # plan metadata
    plan = _as_dict(m.get("plan"))
    plan_path = plan.get("path") if isinstance(plan.get("path"), str) else None
    plan_sha256 = plan.get("sha256") if isinstance(plan.get("sha256"), str) else None
    plan_config = _as_dict(plan.get("config"))

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
    )


def list_runs(repo: FileRepository) -> list[RunListItem]:
    items: list[RunListItem] = []
    for p in repo.list_manifest_paths():
        try:
            m = repo.read_json(p)
        except Exception:
            continue
        if str(m.get("kind")) != "promotion_manifest":
            continue

        runtime_id = str(m.get("runtime_id", ""))
        created_at = str(m.get("created_at")) if m.get("created_at") is not None else None

        plan = _as_dict(m.get("plan"))
        plan_sha256 = plan.get("sha256") if isinstance(plan.get("sha256"), str) else None
        cfg = _as_dict(plan.get("config"))
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

        items.append(
            RunListItem(
                runtime_id=runtime_id,
                created_at=created_at,
                approved=approved,
                router_mode=router_mode,
                universe_symbols=universe_symbols,
                strategy_names=strategy_names,
                plan_sha256=plan_sha256,
                manifest_path=str(p),
            )
        )
    # newest first by created_at then manifest filename (stable)
    items.sort(
        key=lambda x: (
            _manifest_ts(x.manifest_path),
            x.runtime_id,
            Path(x.manifest_path).name,
        ),
        reverse=True,
    )
    return items
