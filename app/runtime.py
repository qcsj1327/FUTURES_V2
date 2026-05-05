from __future__ import annotations

from dataclasses import dataclass, replace

from adapters.broker.base import BrokerAdapter
from adapters.marketdata.base import MarketDataAdapter
from app.runtime_config import RuntimeConfig
from core.execution.execution_engine import ExecutionEngine
from core.execution.lifecycle_reasons import (
    BLOCKED_BY_PENDING_ORDER,
    CANCELED,
    DUPLICATE_SAME_TICK,
    EXPIRED,
    HALTED_BY_GUARD,
    NEW,
    RATE_LIMITED,
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
    encode_execution_event,
    encode_order_event,
)
from core.services.trade.exit_service import ExitService
from core.state.state_engine import StateEngine
from core.trigger.trigger_engine import TriggerEngine
from domain.enums import ExecutionStatus
from domain.execution import ExecutionOrder, ExecutionResult
from domain.risk import RiskDecision
from domain.signal import SignalDecision
from domain.state import PortfolioState
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


class Runtime:
    def __init__(
        self,
        config: RuntimeConfig | None = None,
        *,
        market_data: MarketDataAdapter,
        broker: BrokerAdapter,
        state: StateEngine | None = None,
        strategy: Strategy | None = None,
        environment: str = "live",
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
        default_policy = RollPolicy(
            mode="fixed_contract",
            contracts={
                self.config.symbol: f"{self.config.symbol}_main",
                "au": "au_main",
                "ag": "ag_main",
                "rb": "rb_main",
            },
            runtime_id=self.runtime_id,
            env=environment,
            sink=datastore,
        )
        self.instrument_resolver = instrument_resolver or InstrumentResolver(
            roll_policy=default_policy
        )

        self.environment = environment
        self.datastore = datastore
        self.orders_submitted = 0
        self._tick = 0
        self._pending_order_contexts: dict[str, _PendingOrderContext] = {}
        self.max_pending_ticks: int | None = None
        self.symbol_position_limit = SymbolPositionLimit()
        self.portfolio_risk_limits = PortfolioRiskLimits()
        self.initial_equity = 1_000_000.0
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

    def run_market_once(
        self,
        *,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> None:
        quote = self.market_data.get_last_quote(self.config.symbol)
        quote_ts = quote.ts if quote.ts is not None else self._tick
        if not self.trading_calendar.is_trading_time(self.config.symbol, quote_ts):
            self._maybe_save_snapshot()
            return
        decision = self.strategy.generate(self.config.symbol, quote)
        self.run(decision, market_ts=quote_ts)

        for position in list(self.state.portfolio.positions.values()):
            exit_order = self.exit_service.create_exit_order(
                position=position,
                current_price=quote.price,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
            if exit_order is None:
                continue

            exit_result = self.execution.broker.submit_order(exit_order)
            self.record_broker_result(
                exit_order,
                exit_result,
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
            decision,
            symbol=base_symbol,
            instrument_id=base_symbol,
            trade_instrument_id=trade_id,
            runtime_id=self.runtime_id,
            ts=decision.ts if decision.ts is not None else ts,
            bar_ts=decision.bar_ts if decision.bar_ts is not None else ts,
        )

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
        candidate_order = self._candidate_order_from_risk_decision(risk_decision)
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

        order, exec_result = self.execution.execute(risk_decision)

        if order is None:
            self._maybe_append_events(
                order,
                exec_result,
                strategy_name=name,
                strategy_impl=strategy_impl,
                symbol=decision.symbol,
            )
            self.state.apply(order, exec_result)
            self._maybe_save_snapshot()
            return

        self.record_broker_result(
            order,
            exec_result,
            strategy_name=name,
            strategy_impl=strategy_impl,
            symbol=decision.symbol,
        )

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

        self._remember_order_key(order)
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
        self.state.apply(order, exec_result)
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
                self._maybe_append_events(
                    order,
                    result,
                    strategy_name=strategy_name,
                    strategy_impl=strategy_impl,
                    symbol=symbol,
                    write_order_event=False,
                )
                self.state.apply(order, result, strategy_name=strategy_name)
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
    ) -> None:
        if self.datastore is None:
            return

        base = build_base_event(
            ts=self._tick,
            runtime_id=self.runtime_id,
            env=self.environment,
            strategy_name=strategy_name,
            symbol=symbol or self.config.symbol,
            strategy_impl=strategy_impl,
        )

        order_payload = encode_order_event(order)
        if write_order_event and order_payload:
            self.datastore.append_order_event(
                {**base, **order_payload},
                env=self.environment,
            )

        if getattr(exec_result, "status", None) == ExecutionStatus.SUBMITTED:
            return

        exec_payload = encode_execution_event(exec_result)
        order_id = getattr(exec_result, "order_id", None)
        cost_payload = self._cost_payload(order_id)
        self.datastore.append_fill_event(
            {**base, **exec_payload, **cost_payload},
            env=self.environment,
        )

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
            env=self.environment,
            strategy_name=strategy_name,
            symbol=symbol or order.instrument_id,
            strategy_impl=strategy_impl,
        )
        self.datastore.append_order_lifecycle_event(
            {
                **base,
                "event_type": "order_lifecycle",
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
                "reason": reason,
                **self._cost_payload(exec_result.order_id),
            },
            env=self.environment,
        )

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
            stop_loss=decision.stop_loss,
            take_profit=decision.take_profit,
        )

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

        self._refresh_portfolio_metrics()
        self.datastore.save_portfolio_snapshot(
            ts=self._tick,
            portfolio=self.state.portfolio,
            env=self.environment,
        )
        self._tick += 1

    def _refresh_portfolio_metrics(self) -> PortfolioMetrics:
        metrics = self._current_portfolio_metrics()
        self._max_risk_ratio_seen = max(self._max_risk_ratio_seen, metrics.risk_ratio)
        metadata = dict(self.state.portfolio.metadata)
        metadata.update(metrics.as_metadata())
        metadata["max_risk_ratio_seen"] = self._max_risk_ratio_seen
        if self._last_portfolio_sync:
            metadata["portfolio_sync"] = dict(self._last_portfolio_sync)
        self.state.portfolio = PortfolioState(
            runtime_id=self.state.portfolio.runtime_id,
            positions=self.state.portfolio.positions,
            cash=metrics.cash,
            equity=metrics.equity,
            realized_pnl=metrics.realized_pnl,
            unrealized_pnl=metrics.unrealized_pnl,
            updated_ts=self.state.portfolio.updated_ts,
            metadata=metadata,
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
        return self._apply_broker_portfolio_sync(metrics)

    def _apply_broker_portfolio_sync(self, metrics: PortfolioMetrics) -> PortfolioMetrics:
        snapshot_fn = getattr(self.execution.broker, "portfolio_snapshot", None)
        if not callable(snapshot_fn):
            self._last_portfolio_sync = {}
            return metrics
        raw = snapshot_fn()
        if not isinstance(raw, dict):
            self._last_portfolio_sync = {}
            return metrics
        self._last_portfolio_sync = dict(raw)
        equity = _float_or(metrics.equity, raw.get("equity"))
        cash = _float_or(metrics.cash, raw.get("cash"))
        margin_used = _float_or(metrics.margin_used, raw.get("margin_used"))
        risk_ratio = margin_used / equity if equity > 0 else 0.0
        return PortfolioMetrics(
            cash=cash,
            equity=equity,
            margin_used=margin_used,
            risk_ratio=risk_ratio,
            unrealized_pnl=metrics.unrealized_pnl,
            realized_pnl=metrics.realized_pnl,
            notional_by_symbol=metrics.notional_by_symbol,
            margin_by_symbol=metrics.margin_by_symbol,
            cost_total_sum=metrics.cost_total_sum,
        )

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


def _float_or(default: float, value: object) -> float:
    return float(value) if isinstance(value, (int, float)) else default
