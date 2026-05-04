from __future__ import annotations

import json
from pathlib import Path

import pytest

from config.loader import load_plan


def test_runtime_mode_rejects_conflicting_marketdata_mode(tmp_path: Path) -> None:
    cfg = tmp_path / "plan.json"
    cfg.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "env": "dev",
                "universe": {"symbols": ["au"]},
                "runtime": {"mode": "tqkq_sim", "ticks_live": 1, "ticks_sandbox": 0},
                "adapters": {"market_data": {"mode": "live_file", "prices_path": "prices.json"}},
                "instruments": {
                    "roll_policy": {
                        "mode": "fixed_contract",
                        "contracts": {"au": "SHFE.au2406"},
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc:
        load_plan(cfg, runtime_id="rt_conflict")
    msg = str(exc.value)
    assert "runtime.mode=tqkq_sim conflict" in msg
    assert "adapters.market_data.mode" in msg
    assert "expected='tqkq'" in msg
    assert "actual='live_file'" in msg
