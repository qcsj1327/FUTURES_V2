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
    patterns = {
        "summaries": [f"current_{runtime_id}.json", f"candidate_{runtime_id}.json"],
        "decisions": [f"decision_{runtime_id}_*.json"],
        "approved": [f"approved_cand_{runtime_id}.json", f"approved_cand_{runtime_id}_*.json"],
        "manifests": [f"manifest_{runtime_id}_*.json"],
        "strategy_switch": [
            f"strategy_switch_proposal_{runtime_id}.json",
            f"strategy_switch_approved_{runtime_id}.json",
        ],
    }
    for subdir, globs in patterns.items():
        root = artifacts_root / subdir
        if not root.exists():
            continue
        for pattern in globs:
            for p in root.glob(pattern):
                if p.is_file():
                    p.unlink()
