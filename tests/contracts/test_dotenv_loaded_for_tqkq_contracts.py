from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from adapters.marketdata.tqkq_market_data import set_tqkq_api_factory_override
from scripts.run_daemon import main as run_daemon_main
from scripts.run_plan import main as run_plan_main


@dataclass
class _Quote:
    last_price: float = 450.0
    volume: float = 1000.0
    datetime: str = "2026-05-04 10:00:00.000000"
    price_tick: float = 0.2
    volume_multiple: float = 1000.0


class _Api:
    def __init__(self) -> None:
        self.q = _Quote()

    def get_quote(self, _sym: str) -> Any:
        return self.q

    def wait_update(self, deadline: float | None = None) -> bool:
        _ = deadline
        return True

    def close(self) -> None:
        return


def _write_tqkq_mode_plan(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "env": "dev",
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
                "runtime": {
                    "mode": "tqkq_sim",
                    "warmup_seconds": 1,
                    "ticks_live": 1,
                    "ticks_sandbox": 0,
                    "default_quantity": 1.0,
                },
                "instruments": {
                    "roll_policy": {
                        "mode": "fixed_contract",
                        "contracts": {"au": "SHFE.au2406"},
                    }
                },
                "promotion": {
                    "min_events": 1,
                    "min_success_rate_improvement": -1.0,
                    "max_consecutive_failures": 99,
                },
                "router": {"mode": "priority", "tie_breaker": "priority"},
            }
        ),
        encoding="utf-8",
    )


def test_run_plan_loads_dotenv_for_tqkq(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TQKQ_USER", raising=False)
    monkeypatch.delenv("TQKQ_PASS", raising=False)
    (tmp_path / ".env").write_text("TQKQ_USER=fake_user\nTQKQ_PASS=fake_pass\n", encoding="utf-8")
    cfg = tmp_path / "plan.json"
    _write_tqkq_mode_plan(cfg)
    set_tqkq_api_factory_override(lambda: _Api())
    try:
        assert run_plan_main(["--config", str(cfg), "--runtime-id", "rt_dotenv", "--clean"]) == 0
    finally:
        set_tqkq_api_factory_override(None)


def test_run_daemon_rejects_tqkq_sim_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "plan.json"
    _write_tqkq_mode_plan(cfg)
    with pytest.raises(ValueError, match="run_daemon does not support runtime.mode=tqkq_sim"):
        run_daemon_main(["--config", str(cfg), "--runtime-id", "rt_daemon_tqkq"])
