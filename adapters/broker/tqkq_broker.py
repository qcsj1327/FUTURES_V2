from __future__ import annotations

from collections.abc import Callable
from typing import Any

from adapters.broker.base import BrokerAdapter
from adapters.broker.order.order_id_generator import OrderIdGenerator
from adapters.marketdata.base import MarketDataAdapter
from core.instruments.cost_model import calculate_trade_cost
from core.instruments.specs import InstrumentSpecRegistry
from domain.enums import ExecutionStatus
from domain.execution import ExecutionOrder, ExecutionResult


class TqKqBroker(BrokerAdapter):
    """
    TqKq paper broker.

    This mode never submits live orders. It validates that execution uses a real
    trade_instrument_id from the resolver, then simulates an immediate fill using
    the same cost model as the rest of the runtime.
    """

    def __init__(
        self,
        *,
        market_data: MarketDataAdapter,
        instrument_specs: InstrumentSpecRegistry | None = None,
        order_id_prefix: str = "tqkq_sim_order",
        api_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.market_data = market_data
        self.instrument_specs = instrument_specs or InstrumentSpecRegistry()
        self.order_id_generator = OrderIdGenerator(prefix=order_id_prefix)
        self._api_factory = api_factory
        self._execution_costs: dict[str, dict[str, float | None]] = {}

    def submit_order(self, order: ExecutionOrder) -> ExecutionResult:
        order_id = self.order_id_generator.next_id()
        validation_error = self._validate_order(order)
        if validation_error is not None:
            return ExecutionResult(
                success=False,
                status=ExecutionStatus.REJECTED,
                order_id=order_id,
                reason=validation_error,
                filled_quantity=0.0,
                remaining_quantity=order.quantity,
                avg_fill_price=None,
                fill_price=None,
            )

        quote = self.market_data.get_last_quote(order.instrument_id)
        spec = self.instrument_specs.get(order.instrument_id)
        cost = calculate_trade_cost(
            spec=spec,
            side=order.side,
            qty=order.quantity,
            market_price=quote.price,
        )
        self._execution_costs[order_id] = cost.to_event_fields()

        return ExecutionResult(
            success=True,
            status=ExecutionStatus.FILLED,
            order_id=order_id,
            ts=quote.ts,
            fill_price=cost.fill_price,
            reason="tqkq_sim_fill",
            filled_quantity=order.quantity,
            remaining_quantity=0.0,
            avg_fill_price=cost.fill_price,
        )

    def cost_fields(self, order_id: str) -> dict[str, float | None]:
        return dict(self._execution_costs.get(order_id, {}))

    def _validate_order(self, order: ExecutionOrder) -> str | None:
        trade_id = order.trade_instrument_id
        if not isinstance(trade_id, str) or not trade_id:
            return "missing_trade_instrument_id"
        if trade_id.endswith("_main"):
            return "invalid_trade_instrument_id_main_alias"
        if "." not in trade_id:
            return "invalid_trade_instrument_id_not_real_contract"
        spec = self.instrument_specs.get(order.instrument_id)
        if spec.min_qty is not None and order.quantity < spec.min_qty:
            return "quantity_below_min_qty"
        return None

