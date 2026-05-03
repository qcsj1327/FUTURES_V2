from __future__ import annotations

from adapters.marketdata.base import MarketDataAdapter
from app.runtime import Runtime
from core.signal_router.router import RouterConfig, route
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
        strategy_weights: dict[str, float],
        router_config: RouterConfig,
    ) -> None:
        self.executor = executor
        self.market_data = market_data
        self.symbols = universe_symbols
        self.strategy_set = strategy_set
        self.priorities = strategy_priorities
        self.weights = strategy_weights
        self.router_config = router_config

    def run_tick(self) -> None:
        quotes = self.market_data.get_last_quotes(self.symbols)
        tagged = self.strategy_set.generate(quotes)
        final_tagged = route(
            tagged,
            config=self.router_config,
            priorities=self.priorities,
            weights=self.weights,
        )

        for td in final_tagged:
            base = self.executor.instrument_resolver.base_symbol(
                td.decision.symbol or td.decision.instrument_id or td.strategy_name
            )
            quote = quotes.get(base)
            self.executor.run(
                td.decision,
                strategy_name=td.strategy_name,
                strategy_impl=str(getattr(td, "strategy_impl", "unknown")),
                market_ts=quote.ts if quote is not None else None,
            )

        # optional exit per position (best-effort symbol mapping)
        cfg = self.executor.config
        stop_loss = getattr(cfg, "stop_loss", None)
        take_profit = getattr(cfg, "take_profit", None)

        for pos in list(self.executor.state.portfolio.positions.values()):
            sym = getattr(pos, "instrument_id", None) or getattr(pos, "trade_instrument_id", None)
            if not isinstance(sym, str) or sym not in quotes:
                continue
            raw_quote_ts = quotes[sym].ts
            quote_ts: int = raw_quote_ts if raw_quote_ts is not None else self.executor._tick
            if not self.executor.trading_calendar.is_trading_time(sym, quote_ts):
                continue

            exit_order = self.executor.exit_service.create_exit_order(
                position=pos,
                current_price=quotes[sym].price,
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

        # advance market clock if adapter supports it
        adv = getattr(self.market_data, "advance", None)
        if callable(adv):
            adv()
