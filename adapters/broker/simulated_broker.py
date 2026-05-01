from __future__ import annotations

import time

from adapters.broker.base import BrokerAdapter
from adapters.broker.fill.slippage_model import SlippageModel
from adapters.marketdata.base import MarketDataAdapter
from domain.enums import ExecutionStatus
from domain.execution import ExecutionOrder, ExecutionResult


class SimulatedBroker(BrokerAdapter):
    def __init__(
        self,
        market_data: MarketDataAdapter,
        slippage_rate: float = 0.0,
    ) -> None:
        self.market_data = market_data
        self.slippage_model = SlippageModel(slippage_rate=slippage_rate)
        self._counter = 0

    def submit_order(self, order: ExecutionOrder) -> ExecutionResult:
        self._counter += 1
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
            order_id=f"sim_order_{self._counter}",
            fill_price=fill_price,
            reason="simulated_fill",
        )
