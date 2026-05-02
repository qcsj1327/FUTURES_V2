from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from adapters.storage.datastore_fs import JSONLFileDataStore
from optimize.promoter.manifest_artifact import write_promotion_manifest
from optimize.promoter.promotion_gate import PromotionThresholds
from optimize.promoter.summary_artifact import write_summary_artifact
from research.datastore_replay import summarize_execution_events


def _now_tag() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _artifact_dirs(artifacts_root: Path) -> dict[str, Path]:
    return {
        "summaries": artifacts_root / "summaries",
        "manifests": artifacts_root / "manifests",
    }


def write_daemon_artifacts(
    *,
    runtime_id: str,
    env: str,  # live|sandbox
    store_root: Path,
    artifacts_root: Path,
    candidate_id: str,
    thresholds: PromotionThresholds,
    plan_meta: dict[str, Any] | None,
    write_manifest: bool,
    write_summary: bool,
) -> dict[str, Path | None]:
    dirs = _artifact_dirs(artifacts_root)
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    # Read events from env store
    store = JSONLFileDataStore(
        root_dir=store_root / env,
        env=env,
        runtime_id=runtime_id,
    )
    events = store.read_fill_events(env=env)
    metrics = asdict(summarize_execution_events(events))

    current_path: Path | None = None
    candidate_path: Path | None = None

    if write_summary:
        # daemon 单环境：为了兼容 inspect_run / web readmodel，
        # 直接把同一份 metrics 写入 current_* 与 candidate_* 两个稳定路径。
        current_path = write_summary_artifact(
            runtime_id=runtime_id,
            role="current",
            summary=metrics,
            output_dir=dirs["summaries"],
            filename=f"current_{runtime_id}.json",
        )
        candidate_path = write_summary_artifact(
            runtime_id=runtime_id,
            role="candidate",
            summary=metrics,
            output_dir=dirs["summaries"],
            filename=f"candidate_{runtime_id}.json",
        )

    manifest_path: Path | None = None
    if write_manifest:
        plan_cfg: Mapping[str, Any] | None = None
        plan_path: str | None = None
        plan_sha256: str | None = None

        if plan_meta and isinstance(plan_meta.get("config"), dict):
            plan_cfg = cast(Mapping[str, Any], plan_meta["config"])
            plan_path = cast(str | None, plan_meta.get("path"))
            plan_sha256 = cast(str | None, plan_meta.get("sha256"))

        # 如果 summary 还没写，本次强制写一次（manifest 的签名要求 summary_path）
        if current_path is None or candidate_path is None:
            current_path = write_summary_artifact(
                runtime_id=runtime_id,
                role="current",
                summary=metrics,
                output_dir=dirs["summaries"],
                filename=f"current_{runtime_id}.json",
            )
            candidate_path = write_summary_artifact(
                runtime_id=runtime_id,
                role="candidate",
                summary=metrics,
                output_dir=dirs["summaries"],
                filename=f"candidate_{runtime_id}.json",
            )

        manifest_path = write_promotion_manifest(
            runtime_id=runtime_id,
            candidate_id=candidate_id,
            candidate_config={"env": env},
            thresholds=asdict(thresholds),
            current_summary_path=current_path,
            candidate_summary_path=candidate_path,
            decision_path=None,
            approved_path=None,
            plan=plan_cfg,
            plan_path=plan_path,
            plan_sha256=plan_sha256,
            output_dir=dirs["manifests"],
            filename=f"manifest_{runtime_id}_{_now_tag()}.json",
        )

    return {
        "current_summary_path": current_path,
        "candidate_summary_path": candidate_path,
        "manifest_path": manifest_path,
    }
