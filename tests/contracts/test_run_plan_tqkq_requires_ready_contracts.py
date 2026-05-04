from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from adapters.marketdata.tqkq_market_data import set_tqkq_api_factory_override
from scripts.run_plan import main as run_plan_main


@dataclass
class _Quote:
    last_price: float | None = None
    volume: float | None = None
    datetime: str | None = None


class _Api:
    def __init__(self, *, ready_after: int) -> None:
        self.q = _Quote(last_price=None, volume=None, datetime=None)
        self._calls = 0
        self._ready_after = ready_after

    def get_quote(self, _sym: str) -> Any:
        return self.q

    def wait_update(self, deadline: float | None = None) -> bool:
        _ = deadline
        self._calls += 1
        if self._calls >= self._ready_after:
            self.q.last_price = 100.0
            self.q.volume = 0.0
            self.q.datetime = "2024-06-17 14:59:59.000000"
        return True

    def close(self) -> None:
        return


def _plan(path: Path, *, warmup_seconds: float) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "env": "dev",
                "adapters": {
                    "market_data": {
                        "mode": "tqkq",
                        "prices_path": None,
                        "params": {
                            "tq_symbols": {"au": "SHFE.au2406"},
                            "warmup_seconds": warmup_seconds,
                        },
                    }
                },
                "universe": {"symbols": ["au"]},
                "strategies": [
                    {
                        "name": "simple_strategy",
                        "params": {"force_decision": "HOLD"},
                        "symbols": ["au"],
                        "priority": 1,
                        "weight": 1.0,
                    }
                ],
                "runtime": {"ticks_live": 1, "ticks_sandbox": 0, "default_quantity": 1.0},
                "promotion": {
                    "min_events": 1,
                    "min_success_rate_improvement": -1.0,
                    "max_consecutive_failures": 99,
                },
                "router": {"mode": "priority", "tie_breaker": "priority"},
                "instruments": {
                    "roll_policy": {"mode": "fixed_contract", "contracts": {"au": "SHFE.au2406"}}
                },
            }
        ),
        encoding="utf-8",
    )


def test_run_plan_tqkq_warmup_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "plan.json"
    _plan(cfg, warmup_seconds=1.0)

    api = _Api(ready_after=2)
    set_tqkq_api_factory_override(lambda: api)
    monkeypatch.setenv("TQKQ_USER", "u")
    monkeypatch.setenv("TQKQ_PASS", "p")
    try:
        assert run_plan_main(["--config", str(cfg), "--runtime-id", "rt_tqkq_ok", "--clean"]) == 0
    finally:
        set_tqkq_api_factory_override(None)


def test_run_plan_tqkq_warmup_failure_is_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "plan.json"
    _plan(cfg, warmup_seconds=0.1)

    api = _Api(ready_after=999999)
    set_tqkq_api_factory_override(lambda: api)
    monkeypatch.setenv("TQKQ_USER", "u")
    monkeypatch.setenv("TQKQ_PASS", "p")
    try:
        with pytest.raises(ValueError) as e:
            _ = run_plan_main(["--config", str(cfg), "--runtime-id", "rt_tqkq_fail", "--clean"])
        assert "tqkq warmup failed" in str(e.value)
        assert "warmup_seconds" in str(e.value)
        assert "tq_symbols" in str(e.value)
    finally:
        set_tqkq_api_factory_override(None)

