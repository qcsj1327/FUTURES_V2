from __future__ import annotations

from adapters.marketdata.base import MarketDataAdapter
from app.runtime import Runtime
from core.signal_router.decision_router import route_tagged_signals
from strategies.strategy_set import StrategySet


class UniverseRuntime:
    def __init__(
        self,
        *,
        executor: Runtime,
        market_data: MarketDataAdapter,
        universe_symbols: list[str],
        strategy_set: StrategySet,
        strategy_priorities: dict[str, int],
    ) -> None:
        self.executor = executor
        self.market_data = market_data
        self.symbols = universe_symbols
        self.strategy_set = strategy_set
        self.priorities = strategy_priorities

    def run_tick(self) -> None:
        prices = self.market_data.get_last_prices(self.symbols)
        tagged = self.strategy_set.generate(prices)
        final_tagged = route_tagged_signals(tagged, priorities=self.priorities)

        for td in final_tagged:
            self.executor.run(td.decision, strategy_name=td.strategy_name)

        # optional exit per position (best-effort symbol mapping)
        cfg = self.executor.config
        stop_loss = getattr(cfg, "stop_loss", None)
        take_profit = getattr(cfg, "take_profit", None)

        for pos in list(self.executor.state.portfolio.positions.values()):
            sym = getattr(pos, "instrument_id", None) or getattr(pos, "trade_instrument_id", None)
            if not isinstance(sym, str) or sym not in prices:
                continue

            exit_order = self.executor.exit_service.create_exit_order(
                position=pos,
                current_price=prices[sym],
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
            if exit_order is None:
                continue

            exit_result = self.executor.execution.broker.submit_order(exit_order)
            if exit_result.success:
                self.executor.orders_submitted += 1

            self.executor._maybe_append_events(exit_order, exit_result, strategy_name="exit")
            self.executor.state.apply(exit_order, exit_result, strategy_name="exit")
            self.executor._maybe_save_snapshot()
