from __future__ import annotations

from pathlib import Path
from typing import cast

from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.live_market_data import LiveFileMarketData
from adapters.storage.datastore_fs import JSONLFileDataStore
from app.orchestration.session_builder import build_broker_with_specs, build_instrument_services
from config.instrument_universe import default_symbols
from config.loader import load_plan
from config.models import RunPlan

REAL_CONTRACTS = {
    "au": "SHFE.au2606",
    "ag": "SHFE.ag2606",
    "cu": "SHFE.cu2606",
    "rb": "SHFE.rb2610",
    "zn": "SHFE.zn2606",
}

MAIN_QUOTES = {symbol: f"KQ.m@SHFE.{symbol}" for symbol in REAL_CONTRACTS}


def _assert_default_trading_sessions(plan: RunPlan) -> None:
    assert set(plan.instruments.trading_sessions) == set(default_symbols())
    assert all(plan.instruments.trading_sessions[symbol] for symbol in default_symbols())


def _assert_multi_symbol_strategy_mapping(plan: RunPlan) -> None:
    candidates_by_symbol = {
        symbol: sorted(
            strategy.name
            for strategy in plan.strategies
            if symbol in strategy.symbols
        )
        for symbol in default_symbols()
    }
    enabled_by_symbol = plan.strategy_switch.enabled_by_symbol

    assert set(candidates_by_symbol) == set(default_symbols())
    assert all(len(names) >= 3 for names in candidates_by_symbol.values())
    assert enabled_by_symbol == {
        "au": ["volume_trend_filter"],
        "ag": ["volume_spike_breakout"],
        "cu": ["volume_ma_reversion"],
        "rb": ["simple_strategy"],
        "zn": ["volume_observer_guard"],
    }
    assert plan.strategy_switch.approval_required is False


def _assert_dynamic_exit_config(plan: RunPlan) -> None:
    assert plan.runtime.stop_loss_pct is None
    assert plan.runtime.take_profit_pct is None
    assert plan.runtime.dynamic_exit_enabled is True
    assert plan.runtime.dynamic_stop_loss_vol_mult == 3.0
    assert plan.runtime.dynamic_take_profit_vol_mult == 5.0
    assert plan.runtime.dynamic_min_stop_loss_pct == 0.006
    assert plan.runtime.dynamic_min_take_profit_pct == 0.012
    assert plan.runtime.dynamic_max_stop_loss_pct == 0.03
    assert plan.runtime.dynamic_max_take_profit_pct == 0.06


def test_runtime_mode_local_drives_adapters() -> None:
    plan = load_plan(Path("plans/dev.local.json"), runtime_id="rt_local")
    assert plan.universe.symbols == default_symbols()
    _assert_multi_symbol_strategy_mapping(plan)
    assert plan.runtime.mode == "local"
    assert plan.adapters.market_data.mode == "local_file"
    assert plan.adapters.market_data.prices_path is not None
    assert plan.adapters.broker.mode == "simulated"
    assert plan.adapters.broker.params["order_id_prefix"] == "LOCAL-SIM"
    assert plan.execution.min_order_interval_ticks == 1
    assert plan.runtime.active_top_n == 3
    _assert_dynamic_exit_config(plan)
    assert plan.risk.max_risk_ratio == 0.8
    assert plan.instruments.spec_source == "static"
    assert plan.instruments.roll_policy.contracts == REAL_CONTRACTS
    _assert_default_trading_sessions(plan)


def test_runtime_mode_dryrun_drives_adapters() -> None:
    plan = load_plan(Path("plans/dev.dryrun.json"), runtime_id="rt_dryrun")
    _assert_multi_symbol_strategy_mapping(plan)
    assert plan.runtime.mode == "dryrun"
    assert plan.runtime.warmup_seconds == 8.0
    assert plan.adapters.market_data.mode == "tqkq"
    assert plan.adapters.market_data.params["warmup_seconds"] == 8.0
    assert plan.adapters.market_data.params["tq_symbols"] == MAIN_QUOTES
    assert plan.adapters.broker.mode == "tqkq"
    assert plan.adapters.broker.params["submit_mode"] == "dryrun"
    assert plan.execution.min_order_interval_ticks == 1
    assert plan.execution.max_pending_ticks == 2
    assert plan.runtime.active_top_n == 3
    _assert_dynamic_exit_config(plan)
    assert plan.risk.max_risk_ratio == 0.8
    assert plan.instruments.spec_source == "tqkq"
    assert plan.instruments.roll_policy.resolve_from_market_data is True
    assert plan.instruments.roll_policy.contracts == {}
    _assert_default_trading_sessions(plan)


def test_runtime_mode_live_drives_adapters() -> None:
    plan = load_plan(Path("plans/dev.live.json"), runtime_id="rt_live")
    _assert_multi_symbol_strategy_mapping(plan)
    assert plan.runtime.mode == "live"
    assert plan.adapters.market_data.mode == "tqkq"
    assert plan.adapters.market_data.params["tq_symbols"] == MAIN_QUOTES
    assert plan.adapters.broker.mode == "tqkq"
    assert plan.adapters.broker.params["submit_mode"] == "live"
    assert plan.adapters.broker.params["confirm_live_token"] == "rt_live"
    assert plan.execution.min_order_interval_ticks == 1
    assert plan.execution.max_pending_ticks == 2
    assert plan.runtime.active_top_n == 3
    _assert_dynamic_exit_config(plan)
    assert plan.risk.max_risk_ratio == 0.8
    assert plan.instruments.spec_source == "tqkq"
    assert plan.instruments.roll_policy.resolve_from_market_data is True
    assert plan.instruments.roll_policy.contracts == {}
    _assert_default_trading_sessions(plan)


def test_local_instrument_services_keep_simulated_runtime_always_open(tmp_path: Path) -> None:
    plan = load_plan(Path("plans/dev.local.json"), runtime_id="rt_local")
    store = JSONLFileDataStore(root_dir=tmp_path / "local", scope="local", runtime_id="rt_local")

    calendar, _resolver = build_instrument_services(
        plan=plan,
        runtime_id="rt_local",
        scope="local",
        datastore=store,
    )

    assert calendar.is_trading_time("SHFE.au2606", 0)


def test_local_simulated_broker_uses_local_order_id_prefix() -> None:
    plan = load_plan(Path("plans/dev.local.json"), runtime_id="rt_local")
    market_data = LiveFileMarketData(Path("plans/prices.json"))
    broker = build_broker_with_specs(plan, market_data, instrument_specs=None)
    broker = cast(SimulatedBroker, broker)

    order_id = broker.order_id_generator.next_id()

    assert order_id.startswith("LOCAL-SIM_")
