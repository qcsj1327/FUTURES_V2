from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from adapters.broker.base import BrokerAdapter
from adapters.broker.order.order_id_generator import OrderIdGenerator
from adapters.marketdata.base import MarketDataAdapter
from core.execution.lifecycle_reasons import (
    DUPLICATE_SAME_TICK,
    INVALID_TRADE_INSTRUMENT_ID_MAIN_ALIAS,
    INVALID_TRADE_INSTRUMENT_ID_NOT_REAL_CONTRACT,
    MISSING_TRADE_INSTRUMENT_ID,
    ORDER_SUBMITTED,
    QUANTITY_BELOW_MIN_QTY,
)
from core.instruments.specs import InstrumentSpecRegistry
from domain.enums import ExecutionStatus
from domain.execution import ExecutionOrder, ExecutionResult


@dataclass(frozen=True)
class OrderLifecycleUpdate:
    order: ExecutionOrder
    result: ExecutionResult


class TqKqLiveBroker(BrokerAdapter):
    """
    TqKq live broker skeleton.

    The only implemented mode is dry-run. It validates the execution contract
    and returns SUBMITTED so the runtime can track the order lifecycle through
    the existing JSONL path. No real order is submitted.
    """

    def __init__(
        self,
        *,
        market_data: MarketDataAdapter,
        instrument_specs: InstrumentSpecRegistry | None = None,
        order_id_prefix: str = "tqkq_live_dry_order",
        api_factory: Callable[[], Any] | None = None,
        dry_run: bool = True,
    ) -> None:
        self.market_data = market_data
        self.instrument_specs = instrument_specs or InstrumentSpecRegistry()
        self.order_id_generator = OrderIdGenerator(prefix=order_id_prefix)
        self._api_factory = api_factory
        self.dry_run = dry_run
        self._tick = 0
        self._order_keys_by_tick: dict[int, set[tuple[str, str, str, str | None]]] = {}

    def submit_order(self, order: ExecutionOrder) -> ExecutionResult:
        order_id = self.order_id_generator.next_id()
        if not self.dry_run:
            raise ValueError("tqkq_live broker only supports dry_run=true in this PR")
        if self._is_duplicate_order(order):
            return self._reject(order, order_id=order_id, reason=DUPLICATE_SAME_TICK)
        self._remember_order_key(order)
        validation_error = self._validate_order(order)
        if validation_error is not None:
            return self._reject(order, order_id=order_id, reason=validation_error)
        return ExecutionResult(
            success=False,
            status=ExecutionStatus.SUBMITTED,
            order_id=order_id,
            ts=self._tick,
            reason=ORDER_SUBMITTED,
            filled_quantity=0.0,
            remaining_quantity=order.quantity,
            avg_fill_price=None,
            fill_price=None,
        )

    def poll_order_updates(self, tick: int) -> list[OrderLifecycleUpdate]:
        self._tick = tick
        return []

    def cancel_order(self, order_id: str, *, reason: str = "canceled") -> None:
        _ = (order_id, reason)

    def cost_fields(self, order_id: str) -> dict[str, float | None]:
        _ = order_id
        return {}

    def _reject(
        self,
        order: ExecutionOrder,
        *,
        order_id: str,
        reason: str,
    ) -> ExecutionResult:
        return ExecutionResult(
            success=False,
            status=ExecutionStatus.REJECTED,
            order_id=order_id,
            ts=self._tick,
            reason=reason,
            filled_quantity=0.0,
            remaining_quantity=order.quantity,
            avg_fill_price=None,
            fill_price=None,
        )

    def _validate_order(self, order: ExecutionOrder) -> str | None:
        trade_id = order.trade_instrument_id
        if not isinstance(trade_id, str) or not trade_id:
            return MISSING_TRADE_INSTRUMENT_ID
        if trade_id.endswith("_main"):
            return INVALID_TRADE_INSTRUMENT_ID_MAIN_ALIAS
        if "." not in trade_id:
            return INVALID_TRADE_INSTRUMENT_ID_NOT_REAL_CONTRACT
        spec = self.instrument_specs.get(order.instrument_id)
        if spec.min_qty is not None and order.quantity < spec.min_qty:
            return QUANTITY_BELOW_MIN_QTY
        return None

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
