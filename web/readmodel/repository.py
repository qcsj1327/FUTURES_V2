from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class FileRepository:
    def __init__(self, *, artifacts_root: Path) -> None:
        self.artifacts_root = artifacts_root
        self.manifests_dir = artifacts_root / "manifests"

    def list_manifest_paths(self) -> list[Path]:
        if not self.manifests_dir.exists():
            return []
        return sorted(self.manifests_dir.glob("manifest_*.json"))

    def read_json(self, path: Path) -> dict[str, Any]:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"expected json object: {path}")
        return data

    def latest_manifest_for_runtime(self, runtime_id: str) -> Path | None:
        best: tuple[str, Path] | None = None
        for p in self.list_manifest_paths():
            try:
                m = self.read_json(p)
            except Exception:
                continue
            if str(m.get("kind")) != "promotion_manifest":
                continue
            if str(m.get("runtime_id", "")) != runtime_id:
                continue
            created = str(m.get("created_at", ""))
            key = (created, p)
            if best is None or key > best:
                best = key
        return best[1] if best else None
