from __future__ import annotations

import pytest

from adapters.broker.fill.slippage_model import SlippageModel
from domain.enums import Side


def test_slippage_model_buy_increases_price() -> None:
    price = SlippageModel(slippage_rate=0.01).apply(
        market_price=100.0,
        side=Side.BUY,
    )

    assert price == 101.0


def test_slippage_model_sell_decreases_price() -> None:
    price = SlippageModel(slippage_rate=0.01).apply(
        market_price=100.0,
        side=Side.SELL,
    )

    assert price == 99.0


def test_slippage_model_none_side_keeps_price() -> None:
    price = SlippageModel(slippage_rate=0.01).apply(
        market_price=100.0,
        side=Side.NONE,
    )

    assert price == 100.0


def test_slippage_model_rejects_negative_rate() -> None:
    with pytest.raises(ValueError, match="slippage_rate_must_be_non_negative"):
        SlippageModel(slippage_rate=-0.01)
