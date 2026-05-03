from __future__ import annotations

from pathlib import Path


def remove_tree(path: Path) -> None:
    if not path.exists():
        return
    for p in sorted(path.rglob("*"), reverse=True):
        if p.is_file() or p.is_symlink():
            p.unlink()
        else:
            p.rmdir()
    path.rmdir()


def clean_runtime_paths(
    *,
    runtime_id: str,
    store_root: Path,
    artifacts_root: Path,
) -> None:
    remove_tree(store_root / "live" / runtime_id)
    remove_tree(store_root / "sandbox" / runtime_id)
    for subdir in ("summaries", "decisions", "approved", "manifests"):
        root = artifacts_root / subdir
        if not root.exists():
            continue
        for p in root.glob(f"*{runtime_id}*.json"):
            if p.is_file():
                p.unlink()
