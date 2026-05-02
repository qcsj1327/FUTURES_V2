from __future__ import annotations

from pathlib import Path
from typing import Any

from web.readmodel.repository import FileRepository


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

    return {
        "runtime_id": runtime_id,
        "manifest": str(mp),
        "current": _load(cur_ref),
        "candidate": _load(cand_ref),
    }
