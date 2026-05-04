from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass, replace

from adapters.broker.base import BrokerAdapter
from adapters.broker.fill.fill_quantity_model import FillQuantityModel
from adapters.broker.order.order_id_generator import OrderIdGenerator
from adapters.broker.order.order_tracker import OrderTracker
from adapters.broker.order.rejection_policy import RejectionPolicy
from adapters.marketdata.base import MarketDataAdapter
from core.instruments.cost_model import calculate_trade_cost
from core.instruments.specs import (
    InstrumentSpec,
    InstrumentSpecRegistry,
    SlippageModel,
)
from domain.enums import ExecutionStatus
from domain.execution import ExecutionOrder, ExecutionResult


@dataclass(frozen=True)
class OrderLifecycleUpdate:
    order: ExecutionOrder
    result: ExecutionResult


@dataclass
class _PendingOrder:
    order: ExecutionOrder
    submit_tick: int
    partial_emitted: bool = False
    partial_steps: int = 0


class SimulatedBroker(BrokerAdapter):
    def __init__(
        self,
        market_data: MarketDataAdapter,
        slippage_rate: float = 0.0,
        order_id_prefix: str = "sim_order",
        rejection_policy: RejectionPolicy | None = None,
        reject_next_order: bool = False,
        rejected_symbols: Iterable[str] | None = None,
        reject_above_quantity: float | None = None,
        fill_ratio: float = 1.0,
        fill_delay_ticks: int = 0,
        partial_fill_ratio: float = 1.0,
        max_partial_steps: int = 1,
        max_ticks_to_fill: int | None = None,
        no_fill: bool = False,
        instrument_specs: InstrumentSpecRegistry | None = None,
    ) -> None:
        if slippage_rate < 0:
            raise ValueError("slippage_rate_must_be_non_negative")
        if fill_delay_ticks < 0:
            raise ValueError("fill_delay_ticks must be >= 0")
        if partial_fill_ratio <= 0 or partial_fill_ratio > 1:
            raise ValueError("partial_fill_ratio must be > 0 and <= 1")
        if max_ticks_to_fill is not None and max_ticks_to_fill < 1:
            raise ValueError("max_ticks_to_fill must be >= 1")
        if max_partial_steps < 1:
            raise ValueError("max_partial_steps must be >= 1")
        self.market_data = market_data
        self.slippage_rate = slippage_rate
        self.fill_quantity_model = FillQuantityModel(fill_ratio=fill_ratio)
        self.order_id_generator = OrderIdGenerator(prefix=order_id_prefix)
        self.order_tracker = OrderTracker()
        self.instrument_specs = instrument_specs or InstrumentSpecRegistry()
        self.rejection_policy = rejection_policy or RejectionPolicy(
            reject_next_order=reject_next_order,
            rejected_symbols=rejected_symbols,
            reject_above_quantity=reject_above_quantity,
        )
        self.fill_delay_ticks = fill_delay_ticks
        self.partial_fill_ratio = partial_fill_ratio
        self.max_partial_steps = max_partial_steps
        self.max_ticks_to_fill = max_ticks_to_fill
        self.no_fill = no_fill
        self._tick = 0
        self._pending: dict[str, _PendingOrder] = {}
        self._execution_costs: dict[str, dict[str, float | None]] = {}
        self._order_keys_by_tick: dict[int, set[tuple[str, str, str, str | None]]] = {}

    def submit_order(self, order: ExecutionOrder) -> ExecutionResult:
        order_id = self.order_id_generator.next_id()
        ts = self._now_ts()

        self.order_tracker.create(order_id=order_id, order=order)
        if self._is_duplicate_order(order):
            self.order_tracker.reject(order_id=order_id, reason="duplicate_order_same_tick")
            return ExecutionResult(
                success=False,
                status=ExecutionStatus.REJECTED,
                ts=ts,
                order_id=order_id,
                fill_price=None,
                reason="duplicate_order_same_tick",
                filled_quantity=0.0,
                remaining_quantity=order.quantity,
                avg_fill_price=None,
            )
        self._remember_order_key(order)
        self.order_tracker.submit(order_id)

        reject_reason = self.rejection_policy.reject_reason(order)
        if reject_reason is not None:
            self.order_tracker.reject(order_id=order_id, reason=reject_reason)
            return ExecutionResult(
                success=False,
                status=ExecutionStatus.REJECTED,
                ts=ts,
                order_id=order_id,
                fill_price=None,
                reason=reject_reason,
                filled_quantity=None,
                remaining_quantity=None,
                avg_fill_price=None,
            )

        if not order.trade_instrument_id:
            raise ValueError("ExecutionOrder.trade_instrument_id is required")
        spec = self._spec_for(order)
        if spec.min_qty is not None and order.quantity < spec.min_qty:
            self.order_tracker.reject(order_id=order_id, reason="quantity_below_min_qty")
            return ExecutionResult(
                success=False,
                status=ExecutionStatus.REJECTED,
                ts=ts,
                order_id=order_id,
                fill_price=None,
                reason="quantity_below_min_qty",
                filled_quantity=None,
                remaining_quantity=order.quantity,
                avg_fill_price=None,
            )

        if self._delayed_enabled():
            self._pending[order_id] = _PendingOrder(order=order, submit_tick=self._tick)
            return ExecutionResult(
                success=False,
                status=ExecutionStatus.SUBMITTED,
                ts=ts,
                order_id=order_id,
                fill_price=None,
                reason="order_submitted",
                filled_quantity=None,
                remaining_quantity=order.quantity,
                avg_fill_price=None,
            )

        return self._fill_order(order_id=order_id, order=order, quantity_ratio=None, ts=ts)

    def cost_fields(self, order_id: str) -> dict[str, float | None]:
        return dict(self._execution_costs.get(order_id, {}))

    def poll_order_updates(self, tick: int) -> list[OrderLifecycleUpdate]:
        self._tick = tick
        updates: list[OrderLifecycleUpdate] = []

        for order_id in sorted(list(self._pending.keys())):
            pending = self._pending[order_id]
            age = self._tick - pending.submit_tick
            if self.max_ticks_to_fill is not None and age >= self.max_ticks_to_fill:
                self.order_tracker.cancel(order_id=order_id, reason="expired")
                updates.append(
                    OrderLifecycleUpdate(
                        order=pending.order,
                        result=ExecutionResult(
                            success=False,
                            status=ExecutionStatus.REJECTED,
                            ts=self._tick,
                            order_id=order_id,
                            reason="expired",
                            filled_quantity=None,
                            remaining_quantity=pending.order.quantity,
                            avg_fill_price=None,
                        ),
                    )
                )
                del self._pending[order_id]
                continue

            if age < self.fill_delay_ticks:
                continue
            if self.no_fill:
                continue

            if (
                self.partial_fill_ratio < 1.0
                and pending.partial_steps < self.max_partial_steps
            ):
                pending.partial_steps += 1
                ratio = min(0.999999, self.partial_fill_ratio * pending.partial_steps)
                updates.append(
                    OrderLifecycleUpdate(
                        order=pending.order,
                        result=self._fill_order(
                            order_id=order_id,
                            order=pending.order,
                            quantity_ratio=ratio,
                            ts=self._tick,
                        ),
                    )
                )
                pending.partial_emitted = True
                continue

            if pending.partial_emitted and age <= self.fill_delay_ticks:
                continue

            updates.append(
                OrderLifecycleUpdate(
                    order=pending.order,
                    result=self._fill_order(
                        order_id=order_id,
                        order=pending.order,
                        quantity_ratio=1.0,
                        ts=self._tick,
                    ),
                )
            )
            del self._pending[order_id]

        return updates

    def _now_ts(self) -> int:
        return self._tick if self._delayed_enabled() else int(time.time())

    def _delayed_enabled(self) -> bool:
        return (
            self.fill_delay_ticks > 0
            or self.partial_fill_ratio < 1.0
            or self.max_ticks_to_fill is not None
            or self.no_fill
        )

    def cancel_order(self, order_id: str, *, reason: str = "canceled") -> None:
        pending = self._pending.pop(order_id, None)
        if pending is not None:
            self.order_tracker.cancel(order_id=order_id, reason=reason)

    def _fill_order(
        self,
        *,
        order_id: str,
        order: ExecutionOrder,
        quantity_ratio: float | None,
        ts: int,
    ) -> ExecutionResult:
        symbol = order.instrument_id
        spec = self._spec_for(order)
        market_price = self.market_data.get_last_quote(symbol).price
        if quantity_ratio is None:
            fill_quantity = self.fill_quantity_model.apply(order.quantity)
        else:
            fill_quantity = FillQuantityModel(fill_ratio=quantity_ratio).apply(order.quantity)
        cost = calculate_trade_cost(
            spec=spec,
            side=order.side,
            qty=fill_quantity.filled_quantity,
            market_price=market_price,
        )
        fill_price = cost.fill_price
        self._execution_costs[order_id] = cost.to_event_fields()

        self.order_tracker.fill(
            order_id=order_id,
            filled_quantity=fill_quantity.filled_quantity,
            remaining_quantity=fill_quantity.remaining_quantity,
        )

        return ExecutionResult(
            success=True,
            status=fill_quantity.status,
            ts=ts,
            order_id=order_id,
            fill_price=fill_price,
            reason=(
                "simulated_fill"
                if fill_quantity.status == ExecutionStatus.FILLED
                else "simulated_partial_fill"
            ),
            filled_quantity=fill_quantity.filled_quantity,
            remaining_quantity=fill_quantity.remaining_quantity,
            avg_fill_price=fill_price,
        )

    def _spec_for(self, order: ExecutionOrder) -> InstrumentSpec:
        spec = self.instrument_specs.get(order.instrument_id)
        if self.slippage_rate == 0:
            return spec
        return replace(
            spec,
            slippage_model=SlippageModel(mode="bps", value=self.slippage_rate * 10_000.0),
        )

    def _order_key(self, order: ExecutionOrder) -> tuple[str, str, str, str | None]:
        return (
            order.instrument_id,
            getattr(order.side, "value", str(order.side)),
            getattr(order.position_side, "value", str(order.position_side)),
            order.trade_instrument_id,
        )

    def _is_duplicate_order(self, order: ExecutionOrder) -> bool:
        return self._order_key(order) in self._order_keys_by_tick.get(self._tick, set())

    def _remember_order_key(self, order: ExecutionOrder) -> None:
        self._order_keys_by_tick.setdefault(self._tick, set()).add(self._order_key(order))
        for old_tick in list(self._order_keys_by_tick):
            if old_tick != self._tick:
                del self._order_keys_by_tick[old_tick]
