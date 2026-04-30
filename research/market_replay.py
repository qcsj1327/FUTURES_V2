from __future__ import annotations

from app.runtime import Runtime
from research.run_report import RunReport


class MarketReplayRunner:
    def __init__(self, runtime: Runtime | None = None) -> None:
        self.runtime = runtime or Runtime()

    def run(
        self,
        cycles: int,
        *,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> RunReport:
        if cycles < 0:
            raise ValueError("cycles_must_be_non_negative")

        for _ in range(cycles):
            self.runtime.run_market_once(
                stop_loss=stop_loss,
                take_profit=take_profit,
            )

        return RunReport(
            cycles_run=cycles,
            orders_submitted=self.runtime.orders_submitted,
            final_position_qty=self._final_position_qty(),
        )

    def _final_position_qty(self) -> float:
        return sum(
            position.quantity
            for position in self.runtime.state.portfolio.positions.values()
        )
