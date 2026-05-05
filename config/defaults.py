from __future__ import annotations

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
    UniverseSpec,
)


def default_plan(*, runtime_id: str) -> RunPlan:
    return RunPlan(
        schema_version=1,
        env="dev",
        universe=UniverseSpec(symbols=["au"]),
        strategies=[
            StrategySpec(
                name="simple_strategy",
                params={},
                symbols=["au"],
                priority=100,
                weight=1.0,
            ),
        ],
        adapters=AdaptersSpec(),
        runtime=RuntimeSpec(
            runtime_id=runtime_id,
            ticks_live=3,
            ticks_sandbox=3,
            default_quantity=1.0,
            mode="simulated_v2",
            warmup_seconds=None,
            stop_loss=None,
            take_profit=None,
            active_top_n=0,
            rank_window=20,
            rank_metric="signal_strength",
            rank_refresh_every=1,
            rank_emit_events=1,
        ),
        datastore=DataStoreSpec(),
        router=RouterSpec(mode="priority", tie_breaker="priority"),
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
            roll_policy=RollPolicySpec(
                mode="fixed_contract",
                contracts={"au": "au_main", "ag": "ag_main"},
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
