from __future__ import annotations

from collections.abc import Iterable

from app.runtime import Runtime
from app.runtime_config import RuntimeConfig
from core.state.mark_to_market import MarkToMarket
from research.run_report import RunReport


class MarketReplayRunner:
    def __init__(self, runtime: Runtime | None = None) -> None:
        self.runtime = runtime or Runtime()
        self.mark_to_market = MarkToMarket()
        self._latest_prices: dict[str, float] = {}

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
            self._latest_prices.update(self._market_prices())
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

    def run_multi_symbol_shared_portfolio(
        self,
        symbols: Iterable[str],
        cycles: int,
        *,
        default_quantity: float = 1.0,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> RunReport:
        if cycles < 0:
            raise ValueError("cycles_must_be_non_negative")

        symbols = list(symbols)
        if not symbols:
            return RunReport(
                cycles_run=0,
                orders_submitted=0,
                final_position_qty=0.0,
            )

        equity_curve: list[float] = []
        cash_curve: list[float] = []
        position_qty_curve: list[float] = []

        shared_portfolio = self.runtime.state.portfolio
        total_orders_submitted = 0
        shared_prices: dict[str, float] = {}

        for index in range(cycles):
            symbol = symbols[index % len(symbols)]
            runtime = Runtime(
                RuntimeConfig(
                    symbol=symbol,
                    default_quantity=default_quantity,
                )
            )
            runtime.state.portfolio = shared_portfolio
            runtime.run_market_once(
                stop_loss=stop_loss,
                take_profit=take_profit,
            )

            shared_portfolio = runtime.state.portfolio
            total_orders_submitted += runtime.orders_submitted
            self.runtime = runtime

            shared_prices.update(self._market_prices())
            self._latest_prices = dict(shared_prices)

            cash_curve.append(self._cash())
            position_qty_curve.append(self._final_position_qty())
            equity_curve.append(self._equity())

        return RunReport(
            cycles_run=cycles,
            orders_submitted=total_orders_submitted,
            final_position_qty=self._final_position_qty(),
            equity_curve=equity_curve,
            cash_curve=cash_curve,
            position_qty_curve=position_qty_curve,
            max_drawdown=self._max_drawdown(equity_curve),
        )

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

        if not portfolio.positions:
            return self._cash()

        valuation = self.mark_to_market.value(
            portfolio=portfolio,
            prices=self._latest_prices,
        )

        return valuation.equity

    def _market_prices(self) -> dict[str, float]:
        market_data = self.runtime.market_data

        if hasattr(market_data, "snapshot_prices"):
            prices = market_data.snapshot_prices()
            if isinstance(prices, dict):
                return prices

        return {}

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
