from __future__ import annotations

from pathlib import Path
from typing import Any

from web.readmodel.loader import list_runs as rm_list_runs
from web.readmodel.loader import load_run_from_manifest
from web.readmodel.repository import FileRepository
from web.viewmodels.mapper import run_list_item_to_vm, run_to_vm


def list_runs(*, artifacts_root: Path = Path("data/artifacts")) -> list[dict[str, Any]]:
    repo = FileRepository(artifacts_root=artifacts_root)
    return [run_list_item_to_vm(x) for x in rm_list_runs(repo)]


def get_latest_run(
    *,
    runtime_id: str,
    artifacts_root: Path = Path("data/artifacts"),
) -> dict[str, Any]:
    repo = FileRepository(artifacts_root=artifacts_root)
    m = repo.latest_manifest_for_runtime(runtime_id)
    if m is None:
        raise FileNotFoundError(f"no manifest for runtime_id={runtime_id}")
    run = load_run_from_manifest(repo, m)
    return run_to_vm(run)
