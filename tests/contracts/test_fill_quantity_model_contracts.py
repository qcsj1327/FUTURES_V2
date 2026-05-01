from __future__ import annotations

import pytest

from adapters.broker.fill.fill_quantity_model import FillQuantityModel
from domain.enums import ExecutionStatus


def test_full_fill_quantity_model() -> None:
    fill = FillQuantityModel(fill_ratio=1.0).apply(5.0)

    assert fill.filled_quantity == 5.0
    assert fill.remaining_quantity == 0.0
    assert fill.status == ExecutionStatus.FILLED


def test_partial_fill_quantity_model() -> None:
    fill = FillQuantityModel(fill_ratio=0.4).apply(5.0)

    assert fill.filled_quantity == 2.0
    assert fill.remaining_quantity == 3.0
    assert fill.status == ExecutionStatus.PARTIALLY_FILLED


def test_fill_quantity_model_rejects_zero_ratio() -> None:
    with pytest.raises(ValueError, match="fill_ratio_must_be_between_0_and_1"):
        FillQuantityModel(fill_ratio=0.0)


def test_fill_quantity_model_rejects_ratio_above_one() -> None:
    with pytest.raises(ValueError, match="fill_ratio_must_be_between_0_and_1"):
        FillQuantityModel(fill_ratio=1.1)


def test_fill_quantity_model_rejects_invalid_order_quantity() -> None:
    with pytest.raises(ValueError, match="order_quantity_must_be_positive"):
        FillQuantityModel(fill_ratio=1.0).apply(0.0)
