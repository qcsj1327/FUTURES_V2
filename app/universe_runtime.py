from __future__ import annotations

from collections import deque

from adapters.marketdata.base import MarketDataAdapter, MarketQuote, base_symbol
from app.runtime import Runtime
from core.signal_router.router import RouterConfig, route
from domain.enums import Decision, SignalStrength
from strategies.strategy_set import StrategySet, TaggedDecision

_STRENGTH_SCORE = {
    SignalStrength.WEAK: 1.0,
    SignalStrength.MEDIUM: 2.0,
    SignalStrength.STRONG: 3.0,
}


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
        active_top_n: int = 0,
        rank_window: int = 20,
        rank_metric: str = "signal_strength",
        rank_refresh_every: int = 1,
        rank_emit_events: int = 1,
        enabled_strategies_by_symbol: dict[str, list[str]] | None = None,
    ) -> None:
        self.executor = executor
        self.market_data = market_data
        self.symbols = universe_symbols
        self.strategy_set = strategy_set
        self.priorities = strategy_priorities
        self.weights = strategy_weights
        self.router_config = router_config
        self.active_top_n = active_top_n
        self.rank_window = rank_window
        self.rank_metric = rank_metric
        self.rank_refresh_every = rank_refresh_every
        self.rank_emit_events = rank_emit_events
        self.enabled_strategies_by_symbol = (
            {
                base_symbol(sym): sorted(set(names))
                for sym, names in enabled_strategies_by_symbol.items()
            }
            if enabled_strategies_by_symbol is not None
            else self._default_enabled_strategies_by_symbol()
        )
        self._tick = 0
        self._quote_history: dict[str, deque[MarketQuote]] = {
            base_symbol(s): deque(maxlen=max(2, rank_window + 1)) for s in universe_symbols
        }
        self._active_symbols: set[str] = {base_symbol(s) for s in universe_symbols}
        self._last_scores: dict[str, float] = {base_symbol(s): 0.0 for s in universe_symbols}
        self._last_excluded_symbols: dict[str, str] = {}

    def run_tick(self) -> None:
        self.executor.poll_order_lifecycle(self._tick)
        quotes = self.market_data.get_last_quotes(self.symbols)
        self._update_quote_history(quotes)
        tagged = self.strategy_set.generate(quotes)
        self._emit_strategy_score_events(tagged)
        tradable_symbols = self._tradable_symbols(quotes)
        active_symbols = self._select_active_symbols(tagged, tradable_symbols)
        tagged_for_execution = self._filter_tagged(tagged, active_symbols)
        final_tagged = route(
            tagged_for_execution,
            config=self.router_config,
            priorities=self.priorities,
            weights=self.weights,
        )
        self._emit_rank_event(active_symbols)

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
            if self.active_top_n > 0 and base_symbol(sym) not in active_symbols:
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
            self.executor.record_broker_result(
                exit_order,
                exit_result,
                strategy_name="exit",
                strategy_impl="ExitService",
                symbol=sym,
            )

        # advance market clock if adapter supports it
        adv = getattr(self.market_data, "advance", None)
        if callable(adv):
            adv()
        self._tick += 1

    def _update_quote_history(self, quotes: dict[str, MarketQuote]) -> None:
        for sym, quote in quotes.items():
            base = base_symbol(sym)
            history = self._quote_history.setdefault(
                base,
                deque(maxlen=max(2, self.rank_window + 1)),
            )
            history.append(quote)

    def _default_enabled_strategies_by_symbol(self) -> dict[str, list[str]]:
        enabled: dict[str, set[str]] = {base_symbol(s): set() for s in self.symbols}
        for entry in self.strategy_set.entries:
            for sym in entry.symbols:
                enabled.setdefault(base_symbol(sym), set()).add(entry.name)
        return {sym: sorted(names) for sym, names in enabled.items()}

    def _tradable_symbols(self, quotes: dict[str, MarketQuote]) -> set[str]:
        out: set[str] = set()
        for sym in self.symbols:
            base = base_symbol(sym)
            quote = quotes.get(sym) or quotes.get(base)
            ts = quote.ts if quote is not None and quote.ts is not None else self.executor._tick
            if self.executor.trading_calendar.is_trading_time(base, int(ts)):
                out.add(base)
        return out

    def _select_active_symbols(
        self,
        tagged: list[TaggedDecision],
        tradable_symbols: set[str],
    ) -> set[str]:
        if self.active_top_n <= 0:
            active = {base_symbol(s) for s in self.symbols if base_symbol(s) in tradable_symbols}
            self._last_excluded_symbols = {
                base_symbol(s): "non_trading_time"
                for s in self.symbols
                if base_symbol(s) not in tradable_symbols
            }
            self._active_symbols = active
            return active
        if self._tick % self.rank_refresh_every == 0:
            self._last_scores = self._score_symbols(tagged)
            tradable_scores = {
                sym: score
                for sym, score in self._last_scores.items()
                if sym in tradable_symbols
            }
            ranked = sorted(tradable_scores.items(), key=lambda item: (-item[1], item[0]))
            self._active_symbols = {sym for sym, _score in ranked[: self.active_top_n]}
            all_symbols = {base_symbol(s) for s in self.symbols}
            excluded: dict[str, str] = {}
            for sym in sorted(all_symbols - tradable_symbols):
                excluded[sym] = "non_trading_time"
            for sym in sorted(tradable_symbols - self._active_symbols):
                excluded[sym] = "below_top_n"
            self._last_excluded_symbols = excluded
        return set(self._active_symbols)

    def _score_symbols(self, tagged: list[TaggedDecision]) -> dict[str, float]:
        if self.rank_metric == "signal_strength":
            return self._score_from_signals(tagged)
        return self._score_from_quotes()

    def _score_from_signals(self, tagged: list[TaggedDecision]) -> dict[str, float]:
        scores = {base_symbol(s): 0.0 for s in self.symbols}
        for td in tagged:
            sym = base_symbol(td.decision.symbol or td.decision.instrument_id or "")
            if not sym:
                continue
            if td.decision.decision == Decision.HOLD:
                score = 0.0
            else:
                score = _STRENGTH_SCORE.get(td.decision.strength, 0.0)
                score += float(td.decision.confidence)
            scores[sym] = max(scores.get(sym, 0.0), score)
        return scores

    def _score_tagged_decision(self, td: TaggedDecision) -> float:
        if td.decision.decision == Decision.HOLD:
            return 0.0
        score = _STRENGTH_SCORE.get(td.decision.strength, 0.0)
        return score + float(td.decision.confidence)

    def _score_from_quotes(self) -> dict[str, float]:
        scores: dict[str, float] = {}
        for sym in sorted({base_symbol(s) for s in self.symbols}):
            history = list(self._quote_history.get(sym, ()))
            if len(history) < 2:
                scores[sym] = 0.0
                continue
            current = history[-1]
            lookback = (
                history[0]
                if len(history) <= self.rank_window
                else history[-self.rank_window - 1]
            )
            if lookback.price == 0:
                momentum = 0.0
            else:
                momentum = abs(current.price / lookback.price - 1.0)
            volumes = [q.volume for q in history if q.volume is not None]
            if current.volume is None or not volumes:
                vol_term = 1.0
            else:
                avg_volume = sum(volumes) / len(volumes)
                vol_term = current.volume / avg_volume if avg_volume > 0 else 1.0
            scores[sym] = momentum * vol_term
        return scores

    def _filter_tagged(
        self,
        tagged: list[TaggedDecision],
        active_symbols: set[str],
    ) -> list[TaggedDecision]:
        if self.active_top_n <= 0:
            return tagged
        out: list[TaggedDecision] = []
        for td in tagged:
            sym = base_symbol(td.decision.symbol or td.decision.instrument_id or "")
            enabled = set(self.enabled_strategies_by_symbol.get(sym, []))
            if sym in active_symbols and td.strategy_name in enabled:
                out.append(td)
        return out

    def _emit_rank_event(self, active_symbols: set[str]) -> None:
        if self.active_top_n <= 0 or self.rank_emit_events != 1 or self.executor.datastore is None:
            return
        ranked = sorted(self._last_scores.items(), key=lambda item: (-item[1], item[0]))
        active_ranked = [(sym, score) for sym, score in ranked if sym in active_symbols]
        excluded_reasons_count: dict[str, int] = {}
        for reason in self._last_excluded_symbols.values():
            excluded_reasons_count[reason] = excluded_reasons_count.get(reason, 0) + 1
        self.executor.datastore.append_rank_event(
            {
                "event_type": "rank",
                "ts": self._tick,
                "runtime_id": self.executor.runtime_id,
                "env": self.executor.environment,
                "active_top_n": self.active_top_n,
                "active_symbols": sorted(active_symbols),
                "scores": [
                    {"symbol": sym, "score": score}
                    for sym, score in active_ranked[: self.active_top_n]
                ],
                "excluded_symbols_count": max(0, len(self.symbols) - len(active_symbols)),
                "excluded_symbols": [
                    {"symbol": sym, "reason": reason}
                    for sym, reason in sorted(self._last_excluded_symbols.items())
                ],
                "excluded_reasons_count": excluded_reasons_count,
            },
            env=self.executor.environment,
        )

    def _emit_strategy_score_events(self, tagged: list[TaggedDecision]) -> None:
        if self.executor.datastore is None:
            return
        for td in tagged:
            sym = base_symbol(td.decision.symbol or td.decision.instrument_id or "")
            if not sym:
                continue
            self.executor.datastore.append_strategy_score_event(
                {
                    "event_type": "strategy_score",
                    "ts": self._tick,
                    "runtime_id": self.executor.runtime_id,
                    "env": self.executor.environment,
                    "symbol": sym,
                    "strategy_name": td.strategy_name,
                    "strategy_id": td.strategy_name,
                    "strategy_impl": td.strategy_impl,
                    "decision": td.decision.decision.name,
                    "strength": td.decision.strength.name,
                    "confidence": float(td.decision.confidence),
                    "score": self._score_tagged_decision(td),
                },
                env=self.executor.environment,
            )
