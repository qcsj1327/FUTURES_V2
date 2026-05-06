from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from web.api.dashboard import get_run_dashboard
from web.api.events import get_run_events
from web.api.health import health
from web.api.manifests import get_manifest, list_manifests
from web.api.metrics import get_run_metrics
from web.api.runs import get_latest_run, list_runs
from web.viewmodels.mapper import events_to_vm

app = FastAPI(title="futures_v2 web", version="0.1.0")

app.mount("/ui", StaticFiles(directory="web/ui", html=True), name="ui")

@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/ui")



@app.get("/health")
def health_route() -> dict[str, Any]:
    return health()


@app.get("/manifests")
def manifests_route(
    runtime_id: str = Query(default=""),
    limit: int = Query(default=200, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
) -> list[str]:
    rid = runtime_id.strip() or None
    items = list_manifests(runtime_id=rid)
    return items[offset : offset + limit]


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
    approved: str = Query(default=""),
    router_mode: str = Query(default=""),
    strategy: str = Query(default=""),
) -> list[dict[str, Any]]:
    items = list_runs()

    qn = q.strip().lower()
    if qn:
        items = [
            x
            for x in items
            if qn in (x.get("runtime_id") or "").lower()
            or qn in (x.get("router_mode") or "").lower()
            or any(qn in s.lower() for s in (x.get("strategy_names") or []))
        ]

    ap = approved.strip().lower()
    if ap in {"true", "false"}:
        want = ap == "true"
        items = [x for x in items if x.get("approved") is want]

    rm = router_mode.strip()
    if rm:
        items = [x for x in items if x.get("router_mode") == rm]

    st = strategy.strip()
    if st:
        items = [x for x in items if st in (x.get("strategy_names") or [])]

    return items[offset : offset + limit]


@app.get("/runs/{runtime_id}")
def run_latest_route(runtime_id: str) -> dict[str, Any]:
    try:
        return get_latest_run(runtime_id=runtime_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/runs/{runtime_id}/manifest")
def run_latest_manifest_route(runtime_id: str) -> dict[str, Any]:
    from web.readmodel.repository import FileRepository

    repo = FileRepository(artifacts_root=Path("data/artifacts"))
    mp = repo.latest_manifest_for_runtime(runtime_id)
    if mp is None:
        raise HTTPException(status_code=404, detail=f"no manifest for runtime_id={runtime_id}")
    return repo.read_json(mp)


@app.get("/runs/{runtime_id}/events")
def run_events_route(
    runtime_id: str,
    scope: str = Query(default="live"),
    tail: int = Query(default=50, ge=1, le=5000),
    since_ts: int = Query(default=-1),
    event_type: str = Query(default=""),
    strategy_id: str = Query(default=""),
    success: str = Query(default=""),
    limit: int = Query(default=200, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    payload = get_run_events(
        runtime_id=runtime_id,
        scope=scope,
        tail=tail,
        since_ts=None if since_ts < 0 else since_ts,
        event_type=event_type.strip() or None,
        strategy_id=strategy_id.strip() or None,
        success=success.strip() or None,
        limit=limit,
        offset=offset,
    )
    return events_to_vm(payload)


@app.get("/runs/{runtime_id}/dashboard")
def run_dashboard_route(
    runtime_id: str,
    tail: int = Query(default=80, ge=1, le=5000),
) -> dict[str, Any]:
    try:
        return get_run_dashboard(runtime_id=runtime_id, tail=tail)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/runs/{runtime_id}/metrics")
def run_metrics_route(runtime_id: str) -> dict[str, Any]:
    try:
        return get_run_metrics(runtime_id=runtime_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
