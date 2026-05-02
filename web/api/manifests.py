from __future__ import annotations

from pathlib import Path
from typing import Any

from web.readmodel.repository import FileRepository


def list_manifests(
    *,
    artifacts_root: Path = Path("data/artifacts"),
    runtime_id: str | None = None,
) -> list[str]:
    repo = FileRepository(artifacts_root=artifacts_root)

    paths = repo.list_manifest_paths()
    if runtime_id:
        rid = runtime_id.strip()
        paths = [p for p in paths if p.name.startswith(f"manifest_{rid}_")]

    return [p.name for p in paths]


def get_manifest(*, filename: str, artifacts_root: Path = Path("data/artifacts")) -> dict[str, Any]:
    repo = FileRepository(artifacts_root=artifacts_root)
    p = repo.manifests_dir / filename
    if not p.exists():
        raise FileNotFoundError(filename)
    return repo.read_json(p)
