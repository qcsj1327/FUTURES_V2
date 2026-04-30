from __future__ import annotations

from collections.abc import Iterable

from app.runtime import Runtime
from app.runtime_config import RuntimeConfig
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

        equity_curve: list[float] = []
        cash_curve: list[float] = []
        position_qty_curve: list[float] = []

        for _ in range(cycles):
            self.runtime.run_market_once(
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
            cash_curve.append(self._cash())
            position_qty_curve.append(self._final_position_qty())
            equity_curve.append(self._equity())

        return RunReport(
            cycles_run=cycles,
            orders_submitted=self.runtime.orders_submitted,
            final_position_qty=self._final_position_qty(),
            equity_curve=equity_curve,
            cash_curve=cash_curve,
            position_qty_curve=position_qty_curve,
            max_drawdown=self._max_drawdown(equity_curve),
        )

    def run_many_symbols(
        self,
        symbols: Iterable[str],
        cycles: int,
        *,
        default_quantity: float = 1.0,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> dict[str, RunReport]:
        results: dict[str, RunReport] = {}

        for symbol in symbols:
            runtime = Runtime(
                RuntimeConfig(
                    symbol=symbol,
                    default_quantity=default_quantity,
                )
            )
            runner = MarketReplayRunner(runtime)
            results[symbol] = runner.run(
                cycles,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )

        return results

    def _final_position_qty(self) -> float:
        return sum(
            position.quantity
            for position in self.runtime.state.portfolio.positions.values()
        )

    def _cash(self) -> float:
        cash = self.runtime.state.portfolio.cash
        return 0.0 if cash is None else cash

    def _equity(self) -> float:
        portfolio = self.runtime.state.portfolio

        if portfolio.equity is not None:
            return portfolio.equity

        position_value = sum(
            position.quantity * (position.avg_price or 0.0)
            for position in portfolio.positions.values()
        )

        return self._cash() + position_value

    def _max_drawdown(self, equity_curve: list[float]) -> float:
        if not equity_curve:
            return 0.0

        peak = equity_curve[0]
        max_drawdown = 0.0

        for equity in equity_curve:
            peak = max(peak, equity)
            if peak == 0:
                continue
            drawdown = (peak - equity) / peak
            max_drawdown = max(max_drawdown, drawdown)

        return max_drawdown
