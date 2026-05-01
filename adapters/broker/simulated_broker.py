from __future__ import annotations

import time

from adapters.broker.base import BrokerAdapter
from adapters.broker.fill.slippage_model import SlippageModel
from adapters.broker.order.order_id_generator import OrderIdGenerator
from adapters.marketdata.base import MarketDataAdapter
from domain.enums import ExecutionStatus
from domain.execution import ExecutionOrder, ExecutionResult


class SimulatedBroker(BrokerAdapter):
    def __init__(
        self,
        market_data: MarketDataAdapter,
        slippage_rate: float = 0.0,
        order_id_prefix: str = "sim_order",
    ) -> None:
        self.market_data = market_data
        self.slippage_model = SlippageModel(slippage_rate=slippage_rate)
        self.order_id_generator = OrderIdGenerator(prefix=order_id_prefix)

    def submit_order(self, order: ExecutionOrder) -> ExecutionResult:
        symbol = order.trade_instrument_id or order.instrument_id
        market_price = self.market_data.get_last_price(symbol)
        fill_price = self.slippage_model.apply(
            market_price=market_price,
            side=order.side,
        )

        return ExecutionResult(
            success=True,
            status=ExecutionStatus.SUBMITTED,
            ts=int(time.time()),
            order_id=self.order_id_generator.next_id(),
            fill_price=fill_price,
            reason="simulated_fill",
        )
