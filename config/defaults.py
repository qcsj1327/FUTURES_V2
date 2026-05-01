from __future__ import annotations

from config.models import (
    DataStoreSpec,
    PromotionSpec,
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
        runtime=RuntimeSpec(
            runtime_id=runtime_id,
            ticks_live=3,
            ticks_sandbox=3,
            default_quantity=1.0,
            stop_loss=None,
            take_profit=None,
        ),
        datastore=DataStoreSpec(),
        router=RouterSpec(mode="priority", tie_breaker="priority"),
        promotion=PromotionSpec(
            min_events=1,
            min_success_rate_improvement=-1.0,
            max_consecutive_failures=99,
        ),
    )
