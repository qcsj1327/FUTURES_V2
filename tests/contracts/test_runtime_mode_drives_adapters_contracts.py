from __future__ import annotations

from pathlib import Path

from config.loader import load_plan


def test_runtime_mode_simulated_v2_drives_adapters() -> None:
    plan = load_plan(Path("plans/dev.mode_simulated_v2.json"), runtime_id="rt_mode_sim")
    assert plan.runtime.mode == "simulated_v2"
    assert plan.adapters.market_data.mode == "simulated_v2"
    assert plan.adapters.broker.mode == "simulated"
    assert plan.instruments.spec_source == "static"


def test_runtime_mode_live_file_drives_adapters() -> None:
    plan = load_plan(Path("plans/dev.mode_live_file.json"), runtime_id="rt_mode_live_file")
    assert plan.runtime.mode == "live_file"
    assert plan.adapters.market_data.mode == "live_file"
    assert plan.adapters.market_data.prices_path is not None
    assert plan.adapters.broker.mode == "simulated"
    assert plan.instruments.spec_source == "static"


def test_runtime_mode_tqkq_sim_drives_adapters() -> None:
    plan = load_plan(Path("plans/dev.mode_tqkq_sim.json"), runtime_id="rt_mode_tqkq")
    assert plan.runtime.mode == "tqkq_sim"
    assert plan.runtime.warmup_seconds == 8.0
    assert plan.adapters.market_data.mode == "tqkq"
    assert plan.adapters.market_data.params["warmup_seconds"] == 8.0
    assert plan.adapters.market_data.params["tq_symbols"] == {"au": "SHFE.au2406"}
    assert plan.adapters.broker.mode == "tqkq_sim"
    assert plan.instruments.spec_source == "tqkq"
