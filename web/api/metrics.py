from __future__ import annotations

from pathlib import Path
from typing import Any

from web.readmodel.repository import FileRepository
from web.viewmodels.zh_mapping import zh_reason


def _annotate_summary(payload: dict[str, Any]) -> dict[str, Any]:
    # payload is promotion_summary artifact json, keep original, add *_zh inside summary
    out = dict(payload)

    summary_raw = out.get("summary")
    if not isinstance(summary_raw, dict):
        return out

    summary = dict(summary_raw)

    frc_raw = summary.get("failure_reason_counts")
    if isinstance(frc_raw, dict):
        frc_zh: dict[str, int] = {}
        for k, v in frc_raw.items():
            if isinstance(k, str) and isinstance(v, int):
                frc_zh[zh_reason(k)] = v
        summary["failure_reason_counts_zh"] = frc_zh

    tfr_raw = summary.get("top_failure_reasons")
    if isinstance(tfr_raw, list):
        tfr_zh: list[list[Any]] = []
        for item in tfr_raw:
            if (
                isinstance(item, list)
                and len(item) == 2
                and isinstance(item[0], str)
                and isinstance(item[1], int)
            ):
                tfr_zh.append([zh_reason(item[0]), item[1]])
        summary["top_failure_reasons_zh"] = tfr_zh

    out["summary"] = summary
    return out


def get_run_metrics(
    *,
    runtime_id: str,
    artifacts_root: Path = Path("data/artifacts"),
) -> dict[str, Any]:
    repo = FileRepository(artifacts_root=artifacts_root)
    mp = repo.latest_manifest_for_runtime(runtime_id)
    if mp is None:
        raise FileNotFoundError(f"no manifest for runtime_id={runtime_id}")

    m = repo.read_json(mp)
    artifacts_raw = m.get("artifacts")
    artifacts: dict[str, Any] = artifacts_raw if isinstance(artifacts_raw, dict) else {}

    cur_ref = artifacts.get("current_summary")
    cand_ref = artifacts.get("candidate_summary")

    def _load(ref: Any) -> dict[str, Any]:
        if not isinstance(ref, str) or not ref:
            return {}
        p = Path(ref)
        return repo.read_json(p) if p.exists() else {}

    current = _annotate_summary(_load(cur_ref))
    candidate = _annotate_summary(_load(cand_ref))

    return {
        "runtime_id": runtime_id,
        "manifest": str(mp),
        "current": current,
        "candidate": candidate,
    }
