from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query

from web.api.health import health
from web.api.manifests import get_manifest, list_manifests
from web.api.runs import get_latest_run, list_runs

app = FastAPI(title="futures_v2 web", version="0.1.0")


@app.get("/health")
def health_route() -> dict[str, Any]:
    return health()


@app.get("/manifests")
def manifests_route() -> list[str]:
    return list_manifests()


@app.get("/manifests/{filename}")
def manifest_route(filename: str) -> dict[str, Any]:
    try:
        return get_manifest(filename=filename)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/runs")
def runs_route(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    q: str = Query(default=""),
) -> list[dict[str, Any]]:
    items = list_runs()

    if q:
        qn = q.strip().lower()
        items = [
            x
            for x in items
            if qn in (x.get("runtime_id") or "").lower()
            or qn in (x.get("router_mode") or "").lower()
            or any(qn in s.lower() for s in (x.get("strategy_names") or []))
        ]

    return items[offset : offset + limit]


@app.get("/runs/{runtime_id}")
def run_latest_route(runtime_id: str) -> dict[str, Any]:
    try:
        return get_latest_run(runtime_id=runtime_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/runs/{runtime_id}/manifest")
def run_latest_manifest_route(runtime_id: str) -> dict[str, Any]:
    # Return the raw manifest json for debugging.
    from web.readmodel.repository import FileRepository

    repo = FileRepository(artifacts_root=Path("data/artifacts"))
    mp = repo.latest_manifest_for_runtime(runtime_id)
    if mp is None:
        raise HTTPException(status_code=404, detail=f"no manifest for runtime_id={runtime_id}")
    return repo.read_json(mp)
