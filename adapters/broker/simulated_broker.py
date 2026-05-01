from __future__ import annotations

import time
from collections.abc import Iterable

from adapters.broker.base import BrokerAdapter
from adapters.broker.fill.slippage_model import SlippageModel
from adapters.broker.order.order_id_generator import OrderIdGenerator
from adapters.broker.order.rejection_policy import RejectionPolicy
from adapters.marketdata.base import MarketDataAdapter
from domain.enums import ExecutionStatus
from domain.execution import ExecutionOrder, ExecutionResult


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
    ) -> None:
        self.market_data = market_data
        self.slippage_model = SlippageModel(slippage_rate=slippage_rate)
        self.order_id_generator = OrderIdGenerator(prefix=order_id_prefix)
        self.rejection_policy = rejection_policy or RejectionPolicy(
            reject_next_order=reject_next_order,
            rejected_symbols=rejected_symbols,
            reject_above_quantity=reject_above_quantity,
        )

    def submit_order(self, order: ExecutionOrder) -> ExecutionResult:
        order_id = self.order_id_generator.next_id()
        ts = int(time.time())

        reject_reason = self.rejection_policy.reject_reason(order)
        if reject_reason is not None:
            return ExecutionResult(
                success=False,
                status=ExecutionStatus.REJECTED,
                ts=ts,
                order_id=order_id,
                fill_price=None,
                reason=reject_reason,
            )

        symbol = order.trade_instrument_id or order.instrument_id
        market_price = self.market_data.get_last_price(symbol)
        fill_price = self.slippage_model.apply(
            market_price=market_price,
            side=order.side,
        )

        return ExecutionResult(
            success=True,
            status=ExecutionStatus.SUBMITTED,
            ts=ts,
            order_id=order_id,
            fill_price=fill_price,
            reason="simulated_fill",
        )
