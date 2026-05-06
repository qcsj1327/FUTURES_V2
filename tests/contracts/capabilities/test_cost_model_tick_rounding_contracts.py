from __future__ import annotations

from decimal import Decimal

from core.instruments.cost_model import calculate_trade_cost
from core.instruments.specs import CommissionModel, InstrumentSpec, SlippageModel
from domain.enums import Side


def test_cost_model_aligns_fill_price_to_tick_size() -> None:
    spec = InstrumentSpec(
        symbol="x",
        tick_size=0.2,
        multiplier=10.0,
        min_qty=1.0,
        commission_model=CommissionModel(mode="fixed_per_order", value=0.0),
        slippage_model=SlippageModel(mode="ticks", value=0.0),
        margin_rate=None,
    )

    buy = calculate_trade_cost(
        spec=spec,
        side=Side.BUY,
        qty=1.0,
        market_price=100.0,
        fill_price=100.11,
    )
    sell = calculate_trade_cost(
        spec=spec,
        side=Side.SELL,
        qty=1.0,
        market_price=100.0,
        fill_price=100.11,
    )

    assert Decimal(str(buy.fill_price)) % Decimal("0.2") == 0
    assert Decimal(str(sell.fill_price)) % Decimal("0.2") == 0
    assert buy.fill_price == 100.2
    assert sell.fill_price == 100.0
