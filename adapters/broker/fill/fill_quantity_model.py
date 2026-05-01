from __future__ import annotations

from dataclasses import dataclass

from domain.enums import ExecutionStatus


@dataclass(frozen=True)
class FillQuantity:
    filled_quantity: float
    remaining_quantity: float
    status: ExecutionStatus


class FillQuantityModel:
    def __init__(self, fill_ratio: float = 1.0) -> None:
        if fill_ratio <= 0 or fill_ratio > 1:
            raise ValueError("fill_ratio_must_be_between_0_and_1")

        self.fill_ratio = fill_ratio

    def apply(self, order_quantity: float) -> FillQuantity:
        if order_quantity <= 0:
            raise ValueError("order_quantity_must_be_positive")

        filled_quantity = order_quantity * self.fill_ratio
        remaining_quantity = order_quantity - filled_quantity

        status = (
            ExecutionStatus.FILLED
            if remaining_quantity == 0
            else ExecutionStatus.PARTIALLY_FILLED
        )

        return FillQuantity(
            filled_quantity=filled_quantity,
            remaining_quantity=remaining_quantity,
            status=status,
        )
