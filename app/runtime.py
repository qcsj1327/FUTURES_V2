from __future__ import annotations

from dataclasses import dataclass, replace

from adapters.broker.base import BrokerAdapter
from adapters.marketdata.base import MarketDataAdapter
from app.runtime_config import RuntimeConfig
from app.runtime_observations import build_portfolio_metrics_observation
from config.instrument_universe import (
    default_symbols,
    local_quote_profiles_for,
    trade_contracts_for,
)
from core.execution.event_translator import translate_execution_result
from core.execution.execution_engine import ExecutionEngine
from core.execution.execution_request import ExecutionRequest
from core.execution.lifecycle_reasons import (
    BLOCKED_BY_PENDING_ORDER,
    CANCELED,
    DUPLICATE_SAME_TICK,
    EXPIRED,
    HALTED_BY_GUARD,
    NEW,
    RATE_LIMITED,
    ROLL_CANCEL_PENDING,
    ROLL_CLOSE_POSITION,
    ROLL_COOLDOWN_BLOCK,
    validate_lifecycle_reason,
)
from core.instruments.calendar import TradingCalendar
from core.instruments.resolver import InstrumentResolver
from core.instruments.roll_policy import RollPolicy
from core.instruments.specs import InstrumentSpecRegistry
from core.portfolio.portfolio_engine import PortfolioEngine
from core.portfolio.portfolio_metrics import (
    PortfolioMetrics,
    calculate_portfolio_metrics,
)
from core.risk.portfolio_risk_limits import PortfolioRiskLimits
from core.risk.risk_engine import RiskEngine
from core.risk.symbol_position_limit import SymbolPositionLimit
from core.services.runtime.datastore import DataStore
from core.services.runtime.event_codec import (
    build_base_event,
    encode_datastore_event,
    encode_fill_event,
    encode_order_event,
)
from core.services.trade.exit_service import ExitService
from core.state.state_engine import StateEngine
from core.trigger.trigger_engine import TriggerEngine
from domain.enums import Decision, ExecutionStatus, PositionSide, Side
from domain.execution import ExecutionOrder, ExecutionResult
from domain.risk import RiskDecision
from domain.signal import SignalDecision
from domain.state import PositionKey, PositionState
from strategies.base.simple_strategy import StrategyEngine
from strategies.base.strategy import Strategy


@dataclass(frozen=True)
class _PendingOrderContext:
    order: ExecutionOrder
    strategy_name: str
    strategy_impl: str | None
    symbol: str
    submitted_tick: int
    filled_quantity: float = 0.0
    remaining_quantity: float | None = None


_PositionExitKey = tuple[str, str | None, str]
SIMULATED_INITIAL_EQUITY = 1_000_000.0


class Runtime:
    def __init__(
        self,
        config: RuntimeConfig | None = None,
        *,
        market_data: MarketDataAdapter,
        broker: BrokerAdapter,
        state: StateEngine | None = None,
        strategy: Strategy | None = None,
        scope: str = "live",
        datastore: DataStore | None = None,
        runtime_id: str | None = None,
        trading_calendar: TradingCalendar | None = None,
        instrument_resolver: InstrumentResolver | None = None,
    ) -> None:
        self.config = config or RuntimeConfig()
        self.runtime_id = runtime_id or self.config.runtime_id

        self.trigger = TriggerEngine()
        self.portfolio = PortfolioEngine()
        self.risk = RiskEngine()
        self.execution = ExecutionEngine(broker)
        self.state = state or StateEngine(runtime_id=self.runtime_id)
        self.exit_service = ExitService()
        self.strategy = strategy or StrategyEngine()
        self.market_data = market_data
        self.trading_calendar = trading_calendar or TradingCalendar(sessions_by_symbol={})
        symbols = default_symbols()
        default_policy = RollPolicy(
            mode="fixed_contract",
            contracts=trade_contracts_for(symbols),
            runtime_id=self.runtime_id,
            scope=scope,
            sink=datastore,
        )
        self.instrument_resolver = instrument_resolver or InstrumentResolver(
            roll_policy=default_policy
        )

        self.scope = scope
        self.datastore = datastore
        self.orders_submitted = 0
        self._tick = 0
        self._pending_order_contexts: dict[str, _PendingOrderContext] = {}
        self.max_pending_ticks: int | None = None
        self.symbol_position_limit = SymbolPositionLimit()
        self.portfolio_risk_limits = PortfolioRiskLimits()
        self.initial_equity = SIMULATED_INITIAL_EQUITY
        self._cost_total_sum = 0.0
        self._max_risk_ratio_seen = 0.0
        self._order_keys_by_tick: dict[int, set[tuple[str, str, str, str | None]]] = {}
        self._guard_rejection_seq = 0
        self.max_rejects_in_window: int | None = None
        self.reject_window_ticks: int | None = None
        self.halt_ticks: int | None = None
        self.min_order_interval_ticks: int | None = None
        self._guard_reject_ticks: list[int] = []
        self._halt_until_tick: int | None = None
        self._last_order_tick_by_symbol: dict[str, int] = {}
        self._last_portfolio_sync: dict[str, object] = {}
        self._portfolio_metrics_snapshot: dict[str, object] = {}
        self._roll_cooldown_until_tick: dict[str, int] = {}
        self._exit_levels_by_position: dict[
            _PositionExitKey, tuple[float | None, float | None]
        ] = {}

    def run_market_once(
        self,
        *,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> None:
        """Non-canonical local/research helper.

        Production, daemon, live/dryrun and projection validation paths must enter through
        UniverseRuntime.run_tick() or a SessionBuilder-created UniverseSession.
        """
        quote = self.market_data.get_last_quote(self.config.symbol)
        quote_ts = quote.ts if quote.ts is not None else self._tick
        if not self.trading_calendar.is_trading_time(self.config.symbol, quote_ts):
            self._maybe_save_snapshot()
            return
        decision = self.strategy.generate(self.config.symbol, quote)
        self.run(decision, market_ts=quote_ts)

        for position in list(self.state.portfolio.positions.values()):
            self.execute_exit_for_position(
                position=position,
                current_price=quote.price,
                fallback_stop_loss=stop_loss,
                fallback_take_profit=take_profit,
                strategy_name="exit",
                strategy_impl="ExitService",
                symbol=position.instrument_id,
            )

    def run(
        self,
        decision: SignalDecision,
        *,
        strategy_name: str | None = None,
        strategy_impl: str | None = None,
        market_ts: int | None = None,
    ) -> None:
        ts = market_ts if market_ts is not None else decision.ts
        if ts is None:
            ts = self._tick
        base = self._decision_base_symbol(decision)
        if not self.trading_calendar.is_trading_time(base, int(ts)):
            self._maybe_save_snapshot()
            return
        if self._handle_roll_policy_b(
            decision,
            base_symbol=base,
            ts=int(ts),
            strategy_name=strategy_name,
            strategy_impl=strategy_impl,
        ):
            return
        if self._is_open_decision(decision) and self._has_active_position(base):
            self._maybe_save_snapshot()
            return
        prepared = self._inject_instrument(decision, base_symbol=base, ts=int(ts))
        self._run_decision(prepared, strategy_name=strategy_name, strategy_impl=strategy_impl)

    def _decision_base_symbol(self, decision: SignalDecision) -> str:
        for value in (decision.symbol, decision.instrument_id, decision.trade_instrument_id):
            if isinstance(value, str) and value:
                return self.instrument_resolver.base_symbol(value)
        return self.instrument_resolver.base_symbol(self.config.symbol)

    def _inject_instrument(
        self,
        decision: SignalDecision,
        *,
        base_symbol: str,
        ts: int,
    ) -> SignalDecision:
        trade_id = self.instrument_resolver.resolve_trade_instrument_id(base_symbol, ts)
        return replace(
            self._enrich_exit_prices(decision, base_symbol=base_symbol),
            symbol=base_symbol,
            instrument_id=base_symbol,
            trade_instrument_id=trade_id,
            runtime_id=self.runtime_id,
            ts=decision.ts if decision.ts is not None else ts,
            bar_ts=decision.bar_ts if decision.bar_ts is not None else ts,
        )

    def _enrich_exit_prices(
        self,
        decision: SignalDecision,
        *,
        base_symbol: str,
    ) -> SignalDecision:
        if not self._is_open_decision(decision):
            return decision
        quote = None
        reference = decision.expected_price
        if reference is None:
            try:
                quote = self.market_data.get_last_quote(base_symbol)
                reference = quote.price
            except Exception:
                reference = None
        elif self.config.dynamic_exit_enabled:
            try:
                quote = self.market_data.get_last_quote(base_symbol)
            except Exception:
                quote = None
        if reference is None or reference <= 0:
            return decision
        stop_loss = decision.stop_loss
        take_profit = decision.take_profit
        if stop_loss is None:
            stop_loss = self.config.stop_loss
        if take_profit is None:
            take_profit = self.config.take_profit
        if stop_loss is None and self.config.stop_loss_pct is not None:
            stop_loss = self._price_offset(
                reference,
                pct=self.config.stop_loss_pct,
                decision=decision,
                target="stop_loss",
            )
        if take_profit is None and self.config.take_profit_pct is not None:
            take_profit = self._price_offset(
                reference,
                pct=self.config.take_profit_pct,
                decision=decision,
                target="take_profit",
            )
        if self.config.dynamic_exit_enabled:
            if stop_loss is None:
                stop_loss = self._price_offset(
                    reference,
                    pct=self._dynamic_exit_pct(
                        base_symbol=base_symbol,
                        quote=quote,
                        target="stop_loss",
                    ),
                    decision=decision,
                    target="stop_loss",
                )
            if take_profit is None:
                take_profit = self._price_offset(
                    reference,
                    pct=self._dynamic_exit_pct(
                        base_symbol=base_symbol,
                        quote=quote,
                        target="take_profit",
                    ),
                    decision=decision,
                    target="take_profit",
                )
        if stop_loss == decision.stop_loss and take_profit == decision.take_profit:
            return decision
        return replace(decision, stop_loss=stop_loss, take_profit=take_profit)

    def _dynamic_exit_pct(
        self,
        *,
        base_symbol: str,
        quote: object | None,
        target: str,
    ) -> float:
        if target == "stop_loss":
            multiplier = self.config.dynamic_stop_loss_vol_mult
            min_pct = self.config.dynamic_min_stop_loss_pct
            max_pct = self.config.dynamic_max_stop_loss_pct
        else:
            multiplier = self.config.dynamic_take_profit_vol_mult
            min_pct = self.config.dynamic_min_take_profit_pct
            max_pct = self.config.dynamic_max_take_profit_pct
        vol_pct = self._quote_range_pct(quote)
        if vol_pct is None:
            profile = local_quote_profiles_for(default_symbols()).get(base_symbol, {})
            vol_pct = float(profile.get("price_vol", 0.0))
        raw_pct = vol_pct * multiplier
        return min(max_pct, max(min_pct, raw_pct))

    def _quote_range_pct(self, quote: object | None) -> float | None:
        if quote is None:
            return None
        price = float(getattr(quote, "price", 0.0) or 0.0)
        if price <= 0:
            return None
        bars = getattr(quote, "bars", None)
        if not isinstance(bars, dict) or not bars:
            return None
        ranges: list[float] = []
        for timeframe in ("5m", "15m", "1h", "1d"):
            bar = bars.get(timeframe)
            if bar is None:
                continue
            high = getattr(bar, "high", None)
            low = getattr(bar, "low", None)
            if isinstance(high, (int, float)) and isinstance(low, (int, float)) and high >= low:
                ranges.append(float(high - low) / price)
        if not ranges:
            return None
        return max(ranges)

    def _price_offset(
        self,
        reference: float,
        *,
        pct: float,
        decision: SignalDecision,
        target: str,
    ) -> float:
        if pct < 0:
            raise ValueError(f"{target}_pct must be non-negative")
        is_short = decision.decision == Decision.OPEN_SHORT
        if target == "stop_loss":
            multiplier = 1.0 + pct if is_short else 1.0 - pct
        else:
            multiplier = 1.0 - pct if is_short else 1.0 + pct
        return round(reference * multiplier, 6)

    def _handle_roll_policy_b(
        self,
        decision: SignalDecision,
        *,
        base_symbol: str,
        ts: int,
        strategy_name: str | None,
        strategy_impl: str | None,
    ) -> bool:
        intent = self.instrument_resolver.roll_intent(base_symbol, ts)
        if intent is None:
            if self._roll_cooldown_active(base_symbol) and self._is_open_decision(decision):
                trade_id = self.instrument_resolver.resolve_trade_instrument_id(base_symbol, ts)
                self._reject_roll_open(
                    decision,
                    base_symbol=base_symbol,
                    trade_instrument_id=trade_id,
                    reason=ROLL_COOLDOWN_BLOCK,
                    strategy_name=strategy_name,
                    strategy_impl=strategy_impl,
                )
                return True
            return False

        old_contract, new_contract = intent
        if self._cancel_roll_pending(base_symbol):
            self._maybe_save_snapshot()
            return True

        if self._close_roll_positions(base_symbol, old_contract):
            return True

        activated = self.instrument_resolver.activate_roll(base_symbol, ts)
        if activated is not None:
            cooldown_ticks = self.instrument_resolver.roll_cooldown_ticks
            self._roll_cooldown_until_tick[base_symbol] = self._tick + cooldown_ticks

        if self._is_open_decision(decision):
            self._reject_roll_open(
                decision,
                base_symbol=base_symbol,
                trade_instrument_id=new_contract,
                reason=ROLL_COOLDOWN_BLOCK,
                strategy_name=strategy_name,
                strategy_impl=strategy_impl,
            )
            return True
        self._maybe_save_snapshot()
        return True

    def _roll_cooldown_active(self, base_symbol: str) -> bool:
        until = self._roll_cooldown_until_tick.get(base_symbol)
        return until is not None and self._tick < until

    def _is_open_decision(self, decision: SignalDecision) -> bool:
        return decision.decision in {Decision.OPEN_LONG, Decision.OPEN_SHORT}

    def _has_active_position(self, base_symbol: str) -> bool:
        return any(
            position.instrument_id == base_symbol and position.quantity > 0
            for position in self.state.portfolio.positions.values()
        )

    def _reject_roll_open(
        self,
        decision: SignalDecision,
        *,
        base_symbol: str,
        trade_instrument_id: str,
        reason: str,
        strategy_name: str | None,
        strategy_impl: str | None,
    ) -> None:
        order = self._order_from_open_decision(
            decision,
            base_symbol=base_symbol,
            trade_instrument_id=trade_instrument_id,
        )
        name = strategy_name or decision.strategy_name or "main"
        self._append_guard_rejection(
            order,
            reason=reason,
            strategy_name=name,
            strategy_impl=strategy_impl,
            symbol=base_symbol,
            count_for_halt=False,
        )

    def _order_from_open_decision(
        self,
        decision: SignalDecision,
        *,
        base_symbol: str,
        trade_instrument_id: str,
    ) -> ExecutionOrder:
        position_side = decision.position_side
        if position_side is None:
            position_side = (
                PositionSide.SHORT
                if decision.decision == Decision.OPEN_SHORT
                else PositionSide.LONG
            )
        return ExecutionOrder(
            instrument_id=base_symbol,
            trade_instrument_id=trade_instrument_id,
            side=decision.side,
            position_side=position_side,
            quantity=self.config.default_quantity,
            order_type="market",
            price=self._order_limit_price(base_symbol, decision.expected_price),
            stop_loss=decision.stop_loss,
            take_profit=decision.take_profit,
        )

    def _cancel_roll_pending(self, base_symbol: str) -> bool:
        canceled = False
        cancel = getattr(self.execution.broker, "cancel_order", None)
        for order_id, ctx in list(self._pending_order_contexts.items()):
            if ctx.order.instrument_id != base_symbol:
                continue
            result = ExecutionResult(
                success=False,
                status=ExecutionStatus.REJECTED,
                ts=self._tick,
                order_id=order_id,
                reason=ROLL_CANCEL_PENDING,
                filled_quantity=ctx.filled_quantity,
                remaining_quantity=(
                    ctx.remaining_quantity
                    if ctx.remaining_quantity is not None
                    else ctx.order.quantity
                ),
                avg_fill_price=None,
                fill_price=None,
            )
            self._maybe_append_order_lifecycle_event(
                ctx.order,
                result,
                strategy_name=ctx.strategy_name,
                strategy_impl=ctx.strategy_impl,
                symbol=ctx.symbol,
                status_override="CANCELED",
            )
            if callable(cancel):
                cancel(order_id, reason=ROLL_CANCEL_PENDING)
            self._pending_order_contexts.pop(order_id, None)
            canceled = True
        return canceled

    def _close_roll_positions(self, base_symbol: str, old_contract: str) -> bool:
        closed = False
        for position in list(self.state.portfolio.positions.values()):
            if position.instrument_id != base_symbol:
                continue
            if position.trade_instrument_id != old_contract:
                continue
            if position.quantity <= 0:
                continue
            closed = self.execute_close_position(
                position=position,
                current_price=self._order_limit_price(base_symbol, None),
                strategy_name="roll_policy_B",
                strategy_impl="RollPolicy",
                symbol=base_symbol,
                reason=ROLL_CLOSE_POSITION,
            ) or closed
        return closed

    def _run_decision(
        self,
        decision: SignalDecision,
        *,
        strategy_name: str | None = None,
        strategy_impl: str | None = None,
    ) -> None:
        trigger_result = self.trigger.process(
            decision,
            runtime_id=self.runtime_id,
        )
        allocation = self.portfolio.allocate(
            trigger_result,
            default_quantity=self.config.default_quantity,
        )
        name = (
            strategy_name
            or getattr(decision, "strategy_name", None)
            or "main"
        )
        risk_decision = self.risk.evaluate(allocation, portfolio=self.state.portfolio)
        order_price = self._order_limit_price(
            risk_decision.instrument_id,
            decision.expected_price,
        )
        candidate_order = self._candidate_order_from_risk_decision(
            risk_decision,
            order_price=order_price,
        )
        if candidate_order is not None:
            if self._is_halted():
                self._append_guard_rejection(
                    candidate_order,
                    reason=HALTED_BY_GUARD,
                    strategy_name=name,
                    strategy_impl=strategy_impl,
                    symbol=decision.symbol,
                    count_for_halt=False,
                )
                return
            if self._is_rate_limited(candidate_order):
                self._append_guard_rejection(
                    candidate_order,
                    reason=RATE_LIMITED,
                    strategy_name=name,
                    strategy_impl=strategy_impl,
                    symbol=decision.symbol,
                )
                return
            pending_ctx = self._pending_context_for_order(candidate_order)
            if pending_ctx is not None:
                self._append_guard_rejection(
                    candidate_order,
                    reason=BLOCKED_BY_PENDING_ORDER,
                    strategy_name=name,
                    strategy_impl=strategy_impl,
                    symbol=decision.symbol,
                )
                return
            position_limit_reason = self.symbol_position_limit.reject_reason(
                order=candidate_order,
                portfolio=self.state.portfolio,
            )
            if position_limit_reason is not None:
                self._append_guard_rejection(
                    candidate_order,
                    reason=position_limit_reason,
                    strategy_name=name,
                    strategy_impl=strategy_impl,
                    symbol=decision.symbol,
                )
                return
            portfolio_limit_reason = self._portfolio_risk_reject_reason(candidate_order)
            if portfolio_limit_reason is not None:
                self._append_guard_rejection(
                    candidate_order,
                    reason=portfolio_limit_reason,
                    strategy_name=name,
                    strategy_impl=strategy_impl,
                    symbol=decision.symbol,
                )
                return
            if self._is_duplicate_order(candidate_order):
                self._append_guard_rejection(
                    candidate_order,
                    reason=DUPLICATE_SAME_TICK,
                    strategy_name=name,
                    strategy_impl=strategy_impl,
                    symbol=decision.symbol,
                )
                return

        order, exec_result = self.execution.execute_request(
            ExecutionRequest(risk_decision=risk_decision, order_price=order_price)
        )

        if order is None:
            self._maybe_append_events(
                order,
                exec_result,
                strategy_name=name,
                strategy_impl=strategy_impl,
                symbol=decision.symbol,
            )
            self._maybe_save_snapshot()
            return

        self.record_broker_result(
            order,
            exec_result,
            strategy_name=name,
            strategy_impl=strategy_impl,
            symbol=decision.symbol,
        )

    def create_exit_order_for_position(
        self,
        *,
        position: PositionState,
        current_price: float,
        fallback_stop_loss: float | None = None,
        fallback_take_profit: float | None = None,
    ) -> ExecutionOrder | None:
        stop_loss, take_profit = self._exit_levels_for_position(
            position,
            fallback_stop_loss=fallback_stop_loss,
            fallback_take_profit=fallback_take_profit,
        )
        exit_order = self.exit_service.create_exit_order(
            position=position,
            current_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
        if exit_order is None:
            return None
        return replace(
            exit_order,
            price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    def execute_exit_for_position(
        self,
        *,
        position: PositionState,
        current_price: float,
        fallback_stop_loss: float | None = None,
        fallback_take_profit: float | None = None,
        strategy_name: str = "exit",
        strategy_impl: str | None = "ExitService",
        symbol: str | None = None,
        reason: str = "exit_position",
    ) -> bool:
        exit_order = self.create_exit_order_for_position(
            position=position,
            current_price=current_price,
            fallback_stop_loss=fallback_stop_loss,
            fallback_take_profit=fallback_take_profit,
        )
        if exit_order is None:
            return False
        return self.execute_close_position(
            position=position,
            current_price=current_price,
            strategy_name=strategy_name,
            strategy_impl=strategy_impl,
            symbol=symbol,
            reason=reason,
            side=exit_order.side,
        )

    def execute_close_position(
        self,
        *,
        position: PositionState,
        current_price: float | None,
        strategy_name: str,
        strategy_impl: str | None,
        symbol: str | None,
        reason: str,
        side: Side | None = None,
    ) -> bool:
        close_side = side or self._close_side_for_position(position)
        risk_decision = self.risk.authorize_close_position(
            position=position,
            side=close_side,
            reason=reason,
        )
        order, result = self.execution.execute_request(
            ExecutionRequest(
                risk_decision=risk_decision,
                order_price=current_price,
            )
        )
        if result.reason is None:
            result = replace(result, reason=reason)
        if order is None:
            self._maybe_append_events(
                order,
                result,
                strategy_name=strategy_name,
                strategy_impl=strategy_impl,
                symbol=symbol or position.instrument_id,
            )
            self._maybe_save_snapshot()
            return False
        self.record_broker_result(
            order,
            result,
            strategy_name=strategy_name,
            strategy_impl=strategy_impl,
            symbol=symbol or position.instrument_id,
        )
        return True

    def _close_side_for_position(self, position: PositionState) -> Side:
        if position.position_side == PositionSide.LONG:
            return Side.SELL
        if position.position_side == PositionSide.SHORT:
            return Side.BUY
        return Side.NONE

    def record_broker_result(
        self,
        order: ExecutionOrder,
        exec_result: ExecutionResult,
        *,
        strategy_name: str,
        strategy_impl: str | None = None,
        symbol: str | None = None,
    ) -> None:
        event_symbol = symbol or order.instrument_id
        if self._is_duplicate_order(order):
            duplicate = ExecutionResult(
                success=False,
                status=ExecutionStatus.REJECTED,
                ts=self._tick,
                order_id=exec_result.order_id,
                reason=DUPLICATE_SAME_TICK,
                filled_quantity=0.0,
                remaining_quantity=order.quantity,
                avg_fill_price=None,
                fill_price=None,
            )
            self._maybe_append_order_lifecycle_event(
                order,
                duplicate,
                strategy_name=strategy_name,
                strategy_impl=strategy_impl,
                symbol=event_symbol,
            )
            self._maybe_save_snapshot()
            return

        self._maybe_append_order_lifecycle_event(
            order,
            ExecutionResult(
                success=False,
                status=ExecutionStatus.SUBMITTED,
                ts=self._tick,
                order_id=exec_result.order_id,
                reason=NEW,
                filled_quantity=0.0,
                remaining_quantity=order.quantity,
                avg_fill_price=None,
                fill_price=None,
            ),
            strategy_name=strategy_name,
            strategy_impl=strategy_impl,
            symbol=event_symbol,
            status_override="NEW",
        )
        self._maybe_append_order_lifecycle_event(
            order,
            exec_result,
            strategy_name=strategy_name,
            strategy_impl=strategy_impl,
            symbol=event_symbol,
        )
        if exec_result.status == ExecutionStatus.REJECTED:
            self._maybe_save_snapshot()
            return
        self._remember_order_key(order)
        self._maybe_append_events(
            order,
            exec_result,
            strategy_name=strategy_name,
            strategy_impl=strategy_impl,
            symbol=event_symbol,
        )

        if exec_result.order_id is not None and exec_result.status == ExecutionStatus.SUBMITTED:
            self._record_order_tick(order)
            self._pending_order_contexts[exec_result.order_id] = _PendingOrderContext(
                order=order,
                strategy_name=strategy_name,
                strategy_impl=strategy_impl,
                symbol=event_symbol,
                submitted_tick=self._tick,
                filled_quantity=0.0,
                remaining_quantity=order.quantity,
            )
            self._maybe_save_snapshot()
            return

        if exec_result.success:
            self.orders_submitted += 1
            self._record_order_tick(order)

        self._record_execution_cost(exec_result.order_id)
        self._apply_translated_execution_events(
            order,
            exec_result,
            strategy_name=strategy_name,
        )
        self._sync_exit_levels_after_result(order, exec_result)
        self._maybe_save_snapshot()

    def poll_order_lifecycle(self, tick: int) -> None:
        self._expire_pending_orders(tick)
        poll = getattr(self.execution.broker, "poll_order_updates", None)
        if not callable(poll):
            return
        for update in poll(tick):
            order = update.order
            result = update.result
            order_id = result.order_id
            ctx = self._pending_order_contexts.get(order_id or "")
            strategy_name = ctx.strategy_name if ctx is not None else "unknown"
            strategy_impl = ctx.strategy_impl if ctx is not None else None
            symbol = ctx.symbol if ctx is not None else order.instrument_id

            self._maybe_append_order_lifecycle_event(
                order,
                result,
                strategy_name=strategy_name,
                strategy_impl=strategy_impl,
                symbol=symbol,
            )
            if result.status == ExecutionStatus.PARTIALLY_FILLED:
                previous = float(ctx.filled_quantity if ctx is not None else 0.0)
                cumulative = float(result.filled_quantity or 0.0)
                fill_delta = max(0.0, cumulative - previous)
                if fill_delta > 0:
                    self._maybe_append_events(
                        order,
                        result,
                        strategy_name=strategy_name,
                        strategy_impl=strategy_impl,
                        symbol=symbol,
                        write_order_event=False,
                        fill_quantity=fill_delta,
                    )
                    self._apply_translated_execution_events(
                        order,
                        result,
                        strategy_name=strategy_name,
                        fill_quantity=fill_delta,
                    )
                    self._sync_exit_levels_after_result(order, result)
                    self._maybe_save_snapshot()
                if order_id is not None and ctx is not None:
                    self._pending_order_contexts[order_id] = replace(
                        ctx,
                        filled_quantity=float(result.filled_quantity or 0.0),
                        remaining_quantity=result.remaining_quantity,
                    )
                continue
            if result.status == ExecutionStatus.FILLED:
                self.orders_submitted += 1
                self._record_execution_cost(result.order_id)
                previous = float(ctx.filled_quantity if ctx is not None else 0.0)
                cumulative = float(result.filled_quantity or order.quantity)
                fill_delta = max(0.0, cumulative - previous)
                self._maybe_append_events(
                    order,
                    result,
                    strategy_name=strategy_name,
                    strategy_impl=strategy_impl,
                    symbol=symbol,
                    write_order_event=False,
                    fill_quantity=fill_delta,
                )
                self._apply_translated_execution_events(
                    order,
                    result,
                    strategy_name=strategy_name,
                    fill_quantity=fill_delta,
                )
                self._sync_exit_levels_after_result(order, result)
                self._maybe_save_snapshot()
            if order_id is not None:
                self._pending_order_contexts.pop(order_id, None)

    def _maybe_append_events(
        self,
        order: object | None,
        exec_result: object,
        *,
        strategy_name: str,
        strategy_impl: str | None = None,
        symbol: str | None = None,
        write_order_event: bool = True,
        fill_quantity: float | None = None,
    ) -> None:
        if self.datastore is None:
            return

        base = build_base_event(
            ts=self._tick,
            runtime_id=self.runtime_id,
            scope=self.scope,
            strategy_name=strategy_name,
            symbol=symbol or self.config.symbol,
            strategy_impl=strategy_impl,
        )

        if not isinstance(exec_result, ExecutionResult):
            return
        if not isinstance(order, ExecutionOrder):
            return

        translated = translate_execution_result(
            order=order,
            result=exec_result,
            strategy_name=strategy_name,
            runtime_id=self.runtime_id,
            fill_quantity=fill_quantity,
        )

        order_payload = encode_order_event(translated.order_event)
        if write_order_event and translated.order_event is not None and order_payload:
            self.datastore.append_order_event(
                encode_datastore_event(
                    base=base,
                    event_type="order",
                    payload_type="order_event",
                    source="runtime",
                    payload={**order_payload, **self._order_market_payload(order)},
                ),
                scope=self.scope,
            )

        if translated.fill_event is None:
            return
        exec_payload = encode_fill_event(translated.fill_event)
        order_id = translated.fill_event.order_id
        cost_payload = self._cost_payload(order_id)
        self.datastore.append_fill_event(
            encode_datastore_event(
                base=base,
                event_type="fill",
                payload_type="fill_event",
                source="runtime",
                payload={**exec_payload, **cost_payload},
            ),
            scope=self.scope,
        )

    def _apply_translated_execution_events(
        self,
        order: ExecutionOrder,
        exec_result: ExecutionResult,
        *,
        strategy_name: str,
        fill_quantity: float | None = None,
    ) -> None:
        translated = translate_execution_result(
            order=order,
            result=exec_result,
            strategy_name=strategy_name,
            runtime_id=self.runtime_id,
            fill_quantity=fill_quantity,
        )
        if translated.order_event is not None:
            self.state.apply_order_event(translated.order_event)
        if translated.fill_event is not None:
            self.state.apply_fill_event(translated.fill_event)

    def _maybe_append_order_lifecycle_event(
        self,
        order: ExecutionOrder,
        exec_result: ExecutionResult,
        *,
        strategy_name: str,
        strategy_impl: str | None = None,
        symbol: str | None = None,
        status_override: str | None = None,
    ) -> None:
        if self.datastore is None or exec_result.order_id is None:
            return
        status = status_override or self._lifecycle_status(exec_result)
        reason = validate_lifecycle_reason(exec_result.reason)
        if reason == CANCELED:
            status = "CANCELED"
        if reason == EXPIRED:
            status = "EXPIRED"
        base = build_base_event(
            ts=exec_result.ts if exec_result.ts is not None else self._tick,
            runtime_id=self.runtime_id,
            scope=self.scope,
            strategy_name=strategy_name,
            symbol=symbol or order.instrument_id,
            strategy_impl=strategy_impl,
        )
        self.datastore.append_order_lifecycle_event(
            encode_datastore_event(
                base=base,
                event_type="order_lifecycle",
                payload_type="order_lifecycle",
                source="runtime",
                payload={
                    "order_id": exec_result.order_id,
                    "status": status,
                    "instrument_id": order.instrument_id,
                    "trade_instrument_id": order.trade_instrument_id,
                    "side": getattr(order.side, "value", order.side),
                    "position_side": getattr(order.position_side, "value", order.position_side),
                    "quantity": order.quantity,
                    "filled_quantity": exec_result.filled_quantity,
                    "remaining_quantity": exec_result.remaining_quantity,
                    "avg_fill_price": exec_result.avg_fill_price,
                    "price": order.price,
                    "stop_loss": order.stop_loss,
                    "take_profit": order.take_profit,
                    "reason": reason,
                    **self._order_market_payload(order),
                    **self._cost_payload(exec_result.order_id),
                },
            ),
            scope=self.scope,
        )

    def _order_market_payload(self, order: object | None) -> dict[str, object]:
        instrument_id = getattr(order, "instrument_id", None)
        if not isinstance(instrument_id, str) or not instrument_id:
            return {}
        try:
            quote = self.market_data.get_last_quote(instrument_id)
        except Exception:
            return {}
        return {
            "market_price": quote.price,
            "market_volume": quote.volume,
            "market_ts": quote.ts,
        }

    def _cost_payload(self, order_id: object | None) -> dict[str, object]:
        if not isinstance(order_id, str) or not order_id:
            return {}
        costs = getattr(self.execution.broker, "cost_fields", None)
        if not callable(costs):
            return {}
        payload = costs(order_id)
        return payload if isinstance(payload, dict) else {}

    def _record_execution_cost(self, order_id: object | None) -> None:
        payload = self._cost_payload(order_id)
        cost = payload.get("cost_total")
        if isinstance(cost, (int, float)):
            self._cost_total_sum += float(cost)

    def _lifecycle_status(self, exec_result: ExecutionResult) -> str:
        if exec_result.reason == DUPLICATE_SAME_TICK:
            return "REJECTED"
        if exec_result.reason == CANCELED:
            return "CANCELED"
        if exec_result.reason == EXPIRED:
            return "EXPIRED"
        if exec_result.status == ExecutionStatus.SUBMITTED:
            return "SUBMITTED"
        if exec_result.status == ExecutionStatus.PARTIALLY_FILLED:
            return "PARTIAL"
        if exec_result.status == ExecutionStatus.FILLED:
            return "FILLED"
        if exec_result.status == ExecutionStatus.REJECTED:
            return "REJECTED"
        return str(exec_result.status).upper()

    def _order_key(self, order: ExecutionOrder) -> tuple[str, str, str, str | None]:
        return (
            order.instrument_id,
            getattr(order.side, "value", str(order.side)),
            getattr(order.position_side, "value", str(order.position_side)),
            order.trade_instrument_id,
        )

    def _candidate_order_from_risk_decision(
        self,
        decision: RiskDecision,
        *,
        order_price: float | None,
    ) -> ExecutionOrder | None:
        if not decision.allowed:
            return None
        if decision.quantity is None or decision.quantity <= 0:
            return None
        if decision.position_side is None:
            return None
        if not decision.trade_instrument_id:
            return None
        return ExecutionOrder(
            instrument_id=decision.instrument_id,
            trade_instrument_id=decision.trade_instrument_id,
            side=decision.side,
            position_side=decision.position_side,
            quantity=decision.quantity,
            order_type="market",
            price=order_price,
            stop_loss=decision.stop_loss,
            take_profit=decision.take_profit,
        )

    def _order_limit_price(
        self,
        base_symbol: str,
        expected_price: float | None,
    ) -> float | None:
        if expected_price is not None:
            return expected_price
        try:
            return self.market_data.get_last_quote(base_symbol).price
        except Exception:
            return None

    def _pending_context_for_order(
        self,
        order: ExecutionOrder,
    ) -> _PendingOrderContext | None:
        key = self._order_key(order)
        for ctx in self._pending_order_contexts.values():
            if self._order_key(ctx.order) == key:
                return ctx
        return None

    def _append_guard_rejection(
        self,
        order: ExecutionOrder,
        *,
        reason: str,
        strategy_name: str,
        strategy_impl: str | None,
        symbol: str | None,
        count_for_halt: bool = True,
    ) -> None:
        self._guard_rejection_seq += 1
        result = ExecutionResult(
            success=False,
            status=ExecutionStatus.REJECTED,
            ts=self._tick,
            order_id=f"guard_reject_{self._tick}_{self._guard_rejection_seq}",
            reason=reason,
            filled_quantity=0.0,
            remaining_quantity=order.quantity,
            avg_fill_price=None,
            fill_price=None,
        )
        self._maybe_append_order_lifecycle_event(
            order,
            result,
            strategy_name=strategy_name,
            strategy_impl=strategy_impl,
            symbol=symbol or order.instrument_id,
        )
        if count_for_halt:
            self._record_guard_rejection()
        self._maybe_save_snapshot()

    def _portfolio_risk_reject_reason(self, order: ExecutionOrder) -> str | None:
        quote = self.market_data.get_last_quote(order.instrument_id)
        metrics = self._current_portfolio_metrics()
        specs = self._instrument_specs()
        return self.portfolio_risk_limits.reject_reason(
            order=order,
            market_price=quote.price,
            metrics=metrics,
            instrument_specs=specs,
        )

    def _is_duplicate_order(self, order: ExecutionOrder) -> bool:
        return self._order_key(order) in self._order_keys_by_tick.get(self._tick, set())

    def _remember_order_key(self, order: ExecutionOrder) -> None:
        self._order_keys_by_tick.setdefault(self._tick, set()).add(self._order_key(order))
        for old_tick in list(self._order_keys_by_tick):
            if old_tick != self._tick:
                del self._order_keys_by_tick[old_tick]

    def _is_halted(self) -> bool:
        return self._halt_until_tick is not None and self._tick < self._halt_until_tick

    def _record_guard_rejection(self) -> None:
        if self.max_rejects_in_window is None or self.halt_ticks is None:
            return
        window = self.reject_window_ticks or self.max_rejects_in_window
        self._guard_reject_ticks.append(self._tick)
        self._guard_reject_ticks = [
            tick for tick in self._guard_reject_ticks if self._tick - tick < window
        ]
        if len(self._guard_reject_ticks) >= self.max_rejects_in_window:
            self._halt_until_tick = self._tick + self.halt_ticks + 1
            self._guard_reject_ticks = []

    def _is_rate_limited(self, order: ExecutionOrder) -> bool:
        if self.min_order_interval_ticks is None:
            return False
        last = self._last_order_tick_by_symbol.get(order.instrument_id)
        if last is None:
            return False
        return self._tick - last < self.min_order_interval_ticks

    def _record_order_tick(self, order: ExecutionOrder) -> None:
        self._last_order_tick_by_symbol[order.instrument_id] = self._tick

    def _expire_pending_orders(self, tick: int) -> None:
        if self.max_pending_ticks is None:
            return
        for order_id, ctx in list(self._pending_order_contexts.items()):
            if tick - ctx.submitted_tick < self.max_pending_ticks:
                continue
            result = ExecutionResult(
                success=False,
                status=ExecutionStatus.REJECTED,
                ts=tick,
                order_id=order_id,
                reason=EXPIRED,
                filled_quantity=0.0,
                remaining_quantity=(
                    ctx.remaining_quantity
                    if ctx.remaining_quantity is not None
                    else ctx.order.quantity
                ),
                avg_fill_price=None,
                fill_price=None,
            )
            self._maybe_append_order_lifecycle_event(
                ctx.order,
                result,
                strategy_name=ctx.strategy_name,
                strategy_impl=ctx.strategy_impl,
                symbol=ctx.symbol,
            )
            cancel = getattr(self.execution.broker, "cancel_order", None)
            if callable(cancel):
                cancel(order_id, reason=EXPIRED)
            self._pending_order_contexts.pop(order_id, None)

    def _maybe_save_snapshot(self) -> None:
        if self.datastore is None:
            self._refresh_portfolio_metrics()
            self._tick += 1
            return

        metrics = self._refresh_portfolio_metrics()
        self.datastore.save_portfolio_snapshot(
            ts=self._tick,
            portfolio=self.state.portfolio,
            scope=self.scope,
        )
        self.datastore.append_metrics(
            ts=self._tick,
            metrics=self._portfolio_metrics_snapshot or metrics.as_metadata(),
            scope=self.scope,
        )
        self._tick += 1

    def _refresh_portfolio_metrics(self) -> PortfolioMetrics:
        metrics = self._current_portfolio_metrics()
        self._max_risk_ratio_seen = max(self._max_risk_ratio_seen, metrics.risk_ratio)
        self._portfolio_metrics_snapshot = build_portfolio_metrics_observation(
            metrics=metrics,
            max_risk_ratio_seen=self._max_risk_ratio_seen,
            broker_portfolio_sync=self._last_portfolio_sync,
        )
        return metrics

    def _current_portfolio_metrics(self) -> PortfolioMetrics:
        metrics = calculate_portfolio_metrics(
            portfolio=self.state.portfolio,
            prices=self._portfolio_prices(),
            instrument_specs=self._instrument_specs(),
            initial_equity=self.initial_equity,
            cost_total_sum=self._cost_total_sum,
        )
        self._apply_broker_portfolio_sync()
        return metrics

    def _apply_broker_portfolio_sync(self) -> None:
        snapshot_fn = getattr(self.execution.broker, "portfolio_snapshot", None)
        if not callable(snapshot_fn):
            self._last_portfolio_sync = {}
            return
        raw = snapshot_fn()
        if not isinstance(raw, dict):
            self._last_portfolio_sync = {}
            return
        self._last_portfolio_sync = dict(raw)

    def _portfolio_prices(self) -> dict[str, float]:
        symbols = {position.instrument_id for position in self.state.portfolio.positions.values()}
        prices: dict[str, float] = {}
        for symbol in symbols:
            try:
                quote = self.market_data.get_last_quote(symbol)
            except Exception:
                continue
            prices[symbol] = quote.price
        return prices

    def _instrument_specs(self) -> InstrumentSpecRegistry:
        specs = getattr(self.execution.broker, "instrument_specs", None)
        if specs is None:
            return InstrumentSpecRegistry()
        if isinstance(specs, InstrumentSpecRegistry):
            return specs
        return InstrumentSpecRegistry()

    def _sync_exit_levels_after_result(
        self,
        order: ExecutionOrder,
        result: ExecutionResult,
    ) -> None:
        if result.status not in {ExecutionStatus.PARTIALLY_FILLED, ExecutionStatus.FILLED}:
            return
        key = self._position_exit_key_for_order(order)
        if self._is_open_order(order):
            if order.stop_loss is not None or order.take_profit is not None:
                self._exit_levels_by_position[key] = (order.stop_loss, order.take_profit)
            return
        if self._is_close_order(order):
            if order.trade_instrument_id is None:
                return
            position_key = PositionKey(
                instrument_id=order.instrument_id,
                trade_instrument_id=order.trade_instrument_id,
                position_side=order.position_side,
            )
            position = self.state.portfolio.positions.get(position_key)
            if position is None or position.quantity <= 0:
                self._exit_levels_by_position.pop(key, None)

    def _exit_levels_for_position(
        self,
        position: PositionState,
        *,
        fallback_stop_loss: float | None = None,
        fallback_take_profit: float | None = None,
    ) -> tuple[float | None, float | None]:
        stored = self._exit_levels_by_position.get(
            self._position_exit_key_for_position(position)
        )
        if stored is not None:
            return stored
        return (
            fallback_stop_loss if fallback_stop_loss is not None else self.config.stop_loss,
            fallback_take_profit if fallback_take_profit is not None else self.config.take_profit,
        )

    def _position_exit_key_for_order(self, order: ExecutionOrder) -> _PositionExitKey:
        return (
            order.instrument_id,
            order.trade_instrument_id,
            self._enum_value(order.position_side),
        )

    def _position_exit_key_for_position(self, position: PositionState) -> _PositionExitKey:
        return (
            position.instrument_id,
            position.trade_instrument_id,
            self._enum_value(position.position_side),
        )

    def _is_open_order(self, order: ExecutionOrder) -> bool:
        side = self._enum_value(order.side)
        position_side = self._enum_value(order.position_side)
        return (side == "buy" and position_side == "long") or (
            side == "sell" and position_side == "short"
        )

    def _is_close_order(self, order: ExecutionOrder) -> bool:
        side = self._enum_value(order.side)
        position_side = self._enum_value(order.position_side)
        return (side == "sell" and position_side == "long") or (
            side == "buy" and position_side == "short"
        )

    def _enum_value(self, value: object) -> str:
        raw = getattr(value, "value", value)
        return str(raw)
