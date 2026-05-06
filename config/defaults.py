from __future__ import annotations

from config.instrument_universe import default_symbols, trade_contracts_for, trading_sessions_for
from config.models import (
    AdaptersSpec,
    DataStoreSpec,
    ExecutionSpec,
    InstrumentsSpec,
    PromotionSpec,
    RiskSpec,
    RollPolicySpec,
    RouterSpec,
    RunPlan,
    RuntimeSpec,
    StrategySpec,
    StrategySwitchSpec,
    TradingSessionSpec,
    UniverseSpec,
)


def default_plan(*, runtime_id: str) -> RunPlan:
    symbols = default_symbols()
    return RunPlan(
        schema_version=1,
        env="dev",
        universe=UniverseSpec(symbols=symbols),
        strategies=[
            StrategySpec(
                name="simple_strategy",
                params={},
                symbols=symbols,
                priority=100,
                weight=1.0,
            ),
        ],
        adapters=AdaptersSpec(),
        runtime=RuntimeSpec(
            runtime_id=runtime_id,
            ticks_live=3,
            ticks_dryrun=3,
            default_quantity=1.0,
            mode="local",
            warmup_seconds=None,
            stop_loss=None,
            take_profit=None,
            stop_loss_pct=None,
            take_profit_pct=None,
            active_top_n=0,
            rank_window=20,
            rank_metric="signal_strength",
            rank_refresh_every=1,
            rank_emit_events=1,
        ),
        datastore=DataStoreSpec(),
        router=RouterSpec(mode="priority", tie_breaker="priority"),
        strategy_switch=StrategySwitchSpec(
            enabled_by_symbol={symbol: ["simple_strategy"] for symbol in symbols},
            approval_required=False,
            min_score=1.0,
            max_enabled_strategies_per_symbol=1,
        ),
        execution=ExecutionSpec(
            max_pending_ticks=None,
            max_rejects_in_window=None,
            reject_window_ticks=None,
            halt_ticks=None,
            min_order_interval_ticks=None,
        ),
        risk=RiskSpec(
            max_position_qty_by_symbol={},
            max_risk_ratio=None,
            max_margin_used=None,
            max_notional_by_symbol={},
        ),
        instruments=InstrumentsSpec(
            trading_sessions={
                symbol: [
                    TradingSessionSpec(start=session["start"], end=session["end"])
                    for session in sessions
                ]
                for symbol, sessions in trading_sessions_for(symbols).items()
            },
            roll_policy=RollPolicySpec(
                mode="fixed_contract",
                contracts=trade_contracts_for(symbols),
                close_on_roll=False,
                cooldown_ticks=0,
                main_contract_schedule={},
            ),
            spec_source="static",
        ),
        promotion=PromotionSpec(
            min_events=1,
            min_success_rate_improvement=-1.0,
            max_consecutive_failures=99,
        ),
    )
