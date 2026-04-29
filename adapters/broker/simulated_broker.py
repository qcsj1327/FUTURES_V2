from __future__ import annotations

from adapters.broker.base import BrokerAdapter
from adapters.marketdata.base import MarketDataAdapter
from domain.enums import ExecutionStatus
from domain.execution import ExecutionOrder, ExecutionResult


class SimulatedBroker(BrokerAdapter):
    def __init__(self, market_data: MarketDataAdapter) -> None:
        self.market_data = market_data
        self._counter = 0

    def submit_order(self, order: ExecutionOrder) -> ExecutionResult:
        self._counter += 1
        symbol = order.trade_instrument_id or order.instrument_id
        fill_price = self.market_data.get_last_price(symbol)

        return ExecutionResult(
            success=True,
            status=ExecutionStatus.SUBMITTED,
            order_id=f"sim_order_{self._counter}",
            reason=f"filled_at={fill_price}",
        )
