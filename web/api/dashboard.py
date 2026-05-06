from __future__ import annotations

from pathlib import Path
from typing import Any

from web.readmodel.dashboard import inspect_run


def get_run_dashboard(
    *,
    runtime_id: str,
    store_root: Path = Path("data/store"),
    artifacts_root: Path = Path("data/artifacts"),
    tail: int = 80,
) -> dict[str, Any]:
    return inspect_run(
        runtime_id=runtime_id,
        store_root=store_root,
        artifacts_root=artifacts_root,
        tail=tail,
    )
