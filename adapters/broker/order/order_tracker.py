from __future__ import annotations

from dataclasses import dataclass

from domain.enums import OrderStatus, PositionSide, Side
from domain.execution import ExecutionOrder


@dataclass(frozen=True)
class OrderRecord:
    order_id: str
    instrument_id: str
    trade_instrument_id: str | None
    side: Side
    position_side: PositionSide
    requested_quantity: float
    filled_quantity: float
    remaining_quantity: float
    status: OrderStatus
    reason: str | None = None


class OrderTracker:
    def __init__(self) -> None:
        self.records: dict[str, OrderRecord] = {}
        self._history: dict[str, list[OrderStatus]] = {}

    def create(self, *, order_id: str, order: ExecutionOrder) -> OrderRecord:
        if order_id in self.records:
            raise ValueError("duplicate_order_id")

        if order.quantity <= 0:
            raise ValueError("invalid_order_quantity")

        record = OrderRecord(
            order_id=order_id,
            instrument_id=order.instrument_id,
            trade_instrument_id=order.trade_instrument_id,
            side=order.side,
            position_side=order.position_side,
            requested_quantity=order.quantity,
            filled_quantity=0.0,
            remaining_quantity=order.quantity,
            status=OrderStatus.CREATED,
        )
        self._write(record)
        return record

    def submit(self, order_id: str) -> OrderRecord:
        record = self._get(order_id)
        updated = OrderRecord(
            order_id=record.order_id,
            instrument_id=record.instrument_id,
            trade_instrument_id=record.trade_instrument_id,
            side=record.side,
            position_side=record.position_side,
            requested_quantity=record.requested_quantity,
            filled_quantity=record.filled_quantity,
            remaining_quantity=record.remaining_quantity,
            status=OrderStatus.SUBMITTED,
            reason=record.reason,
        )
        self._write(updated)
        return updated

    def fill(
        self,
        *,
        order_id: str,
        filled_quantity: float,
        remaining_quantity: float,
    ) -> OrderRecord:
        record = self._get(order_id)

        if filled_quantity <= 0:
            raise ValueError("invalid_filled_quantity")

        if remaining_quantity < 0:
            raise ValueError("invalid_remaining_quantity")

        if abs((filled_quantity + remaining_quantity) - record.requested_quantity) > 1e-9:
            raise ValueError("fill_quantities_do_not_match_order_quantity")

        status = (
            OrderStatus.FILLED
            if remaining_quantity == 0
            else OrderStatus.PARTIALLY_FILLED
        )

        updated = OrderRecord(
            order_id=record.order_id,
            instrument_id=record.instrument_id,
            trade_instrument_id=record.trade_instrument_id,
            side=record.side,
            position_side=record.position_side,
            requested_quantity=record.requested_quantity,
            filled_quantity=filled_quantity,
            remaining_quantity=remaining_quantity,
            status=status,
            reason=record.reason,
        )
        self._write(updated)
        return updated

    def reject(self, *, order_id: str, reason: str) -> OrderRecord:
        record = self._get(order_id)
        updated = OrderRecord(
            order_id=record.order_id,
            instrument_id=record.instrument_id,
            trade_instrument_id=record.trade_instrument_id,
            side=record.side,
            position_side=record.position_side,
            requested_quantity=record.requested_quantity,
            filled_quantity=0.0,
            remaining_quantity=record.requested_quantity,
            status=OrderStatus.REJECTED,
            reason=reason,
        )
        self._write(updated)
        return updated

    def get(self, order_id: str) -> OrderRecord:
        return self._get(order_id)

    def status_history(self, order_id: str) -> list[OrderStatus]:
        if order_id not in self._history:
            raise ValueError("missing_order_record")
        return list(self._history[order_id])

    def _get(self, order_id: str) -> OrderRecord:
        record = self.records.get(order_id)
        if record is None:
            raise ValueError("missing_order_record")
        return record

    def _write(self, record: OrderRecord) -> None:
        self.records[record.order_id] = record
        self._history.setdefault(record.order_id, []).append(record.status)
