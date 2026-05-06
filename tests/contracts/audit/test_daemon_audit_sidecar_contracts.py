from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.orchestration.daemon_runner import DaemonSession, run_loop
from optimize.promoter.promotion_gate import PromotionThresholds


class _State:
    portfolio: Any = None


class _Broker:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def portfolio_snapshot(self) -> dict[str, object]:
        if self.fail:
            raise RuntimeError("broker unavailable")
        return {}


class _Execution:
    def __init__(self, broker: _Broker) -> None:
        self.broker = broker


class _Executor:
    def __init__(self, broker: _Broker) -> None:
        self.state = _State()
        self.execution = _Execution(broker)


class _Universe:
    def __init__(self, broker: _Broker | None = None) -> None:
        self.ticks = 0
        self.closed = False
        self.executor = _Executor(broker or _Broker())

    def run_tick(self) -> None:
        self.ticks += 1

    def close(self) -> None:
        self.closed = True


def test_daemon_audit_disabled_does_not_run_sidecar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def _sidecar(**_: object) -> None:
        calls.append("called")

    monkeypatch.setattr("app.orchestration.daemon_runner.run_audit_sidecar", _sidecar)
    universe = _Universe()

    ticks = run_loop(
        session=_session(tmp_path, universe=universe, audit_enabled=False),
        max_ticks=1,
        interval_s=0.0,
        stop_on_exception=True,
        artifact_every=0,
    )

    assert ticks == 1
    assert calls == []
    assert universe.closed is True


def test_daemon_audit_enabled_runs_sidecar_outside_main_loop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def _sidecar(**kwargs: object) -> object:
        calls.append(dict(kwargs))
        return object()

    monkeypatch.setattr("app.orchestration.daemon_runner.run_audit_sidecar", _sidecar)
    universe = _Universe()

    ticks = run_loop(
        session=_session(tmp_path, universe=universe, audit_enabled=True),
        max_ticks=1,
        interval_s=0.0,
        stop_on_exception=True,
        artifact_every=0,
    )

    assert ticks == 1
    assert universe.ticks == 1
    assert len(calls) == 1
    assert calls[0]["runtime_profile"] == "live"
    assert calls[0]["datastore_scope"] == "live"


def test_daemon_sidecar_failure_does_not_interrupt_main_loop(tmp_path: Path) -> None:
    universe = _Universe(broker=_Broker(fail=True))

    ticks = run_loop(
        session=_session(tmp_path, universe=universe, audit_enabled=True),
        max_ticks=1,
        interval_s=0.0,
        stop_on_exception=True,
        artifact_every=0,
    )

    assert ticks == 1
    assert universe.ticks == 1
    readiness_files = sorted((tmp_path / "artifacts" / "live" / "audit").glob("readiness_*.json"))
    assert readiness_files
    payload = json.loads(readiness_files[-1].read_text(encoding="utf-8"))
    assert payload["status"] == "degraded"
    assert payload["mutation_allowed"] is False


def test_daemon_local_dryrun_sidecar_remains_diagnostics_only(tmp_path: Path) -> None:
    for scope in ("local", "dryrun"):
        universe = _Universe()
        run_loop(
            session=_session(tmp_path / scope, universe=universe, scope=scope, audit_enabled=True),
            max_ticks=1,
            interval_s=0.0,
            stop_on_exception=True,
            artifact_every=0,
        )

        audit_files = sorted(
            (tmp_path / scope / "artifacts" / scope / "audit").glob("audit_*.json")
        )
        assert audit_files
        payload = json.loads(audit_files[-1].read_text(encoding="utf-8"))
        assert payload["artifact_type"] == "runtime_diagnostics"
        assert payload["diagnostic_only"] is True
        assert payload["is_live"] is False


def _session(
    tmp_path: Path,
    *,
    universe: _Universe,
    scope: str = "live",
    audit_enabled: bool,
) -> DaemonSession:
    return DaemonSession(
        universe_runtime=universe,
        runtime_id=f"rt_{scope}",
        scope=scope,
        store_root=tmp_path / "store",
        artifacts_root=tmp_path / "artifacts",
        thresholds=PromotionThresholds(
            min_events=1,
            min_success_rate_improvement=-1.0,
            max_consecutive_failures=99,
        ),
        plan_meta={"effective_config_summary": {"runtime": {"mode": scope}}},
        candidate_id=f"cand_{scope}",
        audit_enabled=audit_enabled,
        audit_interval_seconds=0.0,
    )
