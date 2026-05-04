from __future__ import annotations

import pytest

from core.instruments.cost_model import calculate_trade_cost
from core.instruments.specs import CommissionModel, InstrumentSpec, SlippageModel
from domain.enums import Side


def test_cost_model_commission_slippage_and_notional_are_deterministic() -> None:
    spec = InstrumentSpec(
        symbol="x",
        tick_size=0.2,
        multiplier=10.0,
        min_qty=1.0,
        commission_model=CommissionModel(mode="bps_notional", value=2.0),
        slippage_model=SlippageModel(mode="ticks", value=2.0),
        margin_rate=0.1,
    )

    cost = calculate_trade_cost(
        spec=spec,
        side=Side.BUY,
        qty=3.0,
        market_price=100.0,
    )

    assert cost.fill_price == 100.4
    assert cost.notional == pytest.approx(3012.0)
    assert cost.commission == pytest.approx(0.6024)
    assert cost.slippage == pytest.approx(12.0)
    assert cost.cost_total == pytest.approx(12.6024)
    assert cost.margin == pytest.approx(301.2)
