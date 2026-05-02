from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any

from optimize.promoter.manifest_artifact import write_promotion_manifest
from optimize.promoter.summary_artifact import write_summary_artifact
from research.datastore_replay import summarize_execution_events


def write_daemon_artifacts(
    *,
    runtime_id: str,
    env: str,  # "live" | "sandbox"
    datastore: Any,  # DataStore-like (must support read_fill_events(env=...))
    candidate_id: str,
    candidate_config: Mapping[str, Any],
    thresholds: Mapping[str, Any],
    plan: Mapping[str, Any] | None,
    plan_path: str | None,
    plan_sha256: str | None,
    artifacts_root: Path,
) -> Path:
    events = datastore.read_fill_events(env=env)
    metrics = asdict(summarize_execution_events(events))

    summaries_dir = artifacts_root / "summaries"
    manifests_dir = artifacts_root / "manifests"
    summaries_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir.mkdir(parents=True, exist_ok=True)

    # For daemon, keep filenames stable so inspect_run can always find something.
    summary_path = write_summary_artifact(
        runtime_id=runtime_id,
        role="current" if env == "live" else "candidate",
        summary=metrics,
        output_dir=summaries_dir,
        filename=f"current_{runtime_id}.json",
    )

    # Minimal manifest for observability tools (decision/approved are None).
    return write_promotion_manifest(
        runtime_id=runtime_id,
        candidate_id=candidate_id,
        candidate_config=candidate_config,
        thresholds=thresholds,
        current_summary_path=summary_path,
        candidate_summary_path=summary_path,
        decision_path=None,
        approved_path=None,
        plan=plan,
        plan_path=plan_path,
        plan_sha256=plan_sha256,
        output_dir=manifests_dir,
        filename=None,
    )
