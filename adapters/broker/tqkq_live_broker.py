from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from adapters.broker.base import BrokerAdapter
from adapters.broker.order.order_id_generator import OrderIdGenerator
from adapters.marketdata.base import MarketDataAdapter
from core.execution.lifecycle_reasons import (
    CANCELED,
    INVALID_TRADE_INSTRUMENT_ID_MAIN_ALIAS,
    INVALID_TRADE_INSTRUMENT_ID_NOT_REAL_CONTRACT,
    MISSING_TRADE_INSTRUMENT_ID,
    ORDER_SUBMITTED,
    QUANTITY_BELOW_MIN_QTY,
    TQKQ_LIVE_FILL,
    TQKQ_LIVE_PARTIAL_FILL,
    TQKQ_LIVE_REJECTED,
)
from core.instruments.cost_model import calculate_trade_cost
from core.instruments.specs import InstrumentSpecRegistry
from domain.enums import ExecutionStatus, PositionSide, Side
from domain.execution import ExecutionOrder, ExecutionResult

_REAL_CONTRACT_RE = re.compile(r"^[A-Z]+\.[A-Za-z]+\d{3,4}$")


@dataclass(frozen=True)
class OrderLifecycleUpdate:
    order: ExecutionOrder
    result: ExecutionResult


@dataclass
class _TrackedOrder:
    order: ExecutionOrder
    native_order: Any | None
    last_status: str
    last_filled_quantity: float = 0.0
    terminal: bool = False


class TqKqLiveBroker(BrokerAdapter):
    """
    TqKq live broker.

    `dry_run=true` is the default and never submits a real order. Non-dry-run
    mode calls a TqApi-like `insert_order` method and polls the returned order
    object. Tests inject a fake API; no contract depends on network access.
    """

    def __init__(
        self,
        *,
        market_data: MarketDataAdapter,
        instrument_specs: InstrumentSpecRegistry | None = None,
        order_id_prefix: str = "tqkq_live_order",
        api_factory: Callable[[], Any] | None = None,
        dry_run: bool = True,
    ) -> None:
        self.market_data = market_data
        self.instrument_specs = instrument_specs or InstrumentSpecRegistry()
        self.order_id_generator = OrderIdGenerator(prefix=order_id_prefix)
        self._api_factory = api_factory
        self.dry_run = dry_run
        self._tick = 0
        self._api: Any | None = None
        self._tracked: dict[str, _TrackedOrder] = {}
        self._execution_costs: dict[str, dict[str, float | None]] = {}
        self._cancel_calls: list[tuple[str, str]] = []

    @property
    def cancel_calls(self) -> list[tuple[str, str]]:
        return list(self._cancel_calls)

    def submit_order(self, order: ExecutionOrder) -> ExecutionResult:
        order_id = self.order_id_generator.next_id()
        validation_error = self._validate_order(order)
        if validation_error is not None:
            return self._reject(order, order_id=order_id, reason=validation_error)

        native_order = None if self.dry_run else self._submit_native_order(order)
        self._tracked[order_id] = _TrackedOrder(
            order=order,
            native_order=native_order,
            last_status="SUBMITTED",
        )
        return ExecutionResult(
            success=False,
            status=ExecutionStatus.SUBMITTED,
            order_id=order_id,
            ts=self._tick,
            reason=ORDER_SUBMITTED,
            filled_quantity=0.0,
            remaining_quantity=order.quantity,
            avg_fill_price=None,
            fill_price=None,
        )

    def poll_order_updates(self, tick: int) -> list[OrderLifecycleUpdate]:
        self._tick = tick
        if self.dry_run:
            return []

        self._wait_update()
        updates: list[OrderLifecycleUpdate] = []
        for order_id, tracked in list(self._tracked.items()):
            if tracked.terminal:
                continue
            state = self._read_native_state(order_id=order_id, tracked=tracked)
            if state.status == tracked.last_status and (
                state.filled_quantity == tracked.last_filled_quantity
            ):
                continue
            tracked.last_status = state.status
            tracked.last_filled_quantity = state.filled_quantity
            if state.terminal:
                tracked.terminal = True
            if state.status in {"PARTIAL", "FILLED"}:
                self._record_cost(
                    order_id=order_id,
                    order=tracked.order,
                    filled_quantity=state.filled_quantity,
                    fill_price=state.avg_fill_price,
                )
            updates.append(
                OrderLifecycleUpdate(
                    order=tracked.order,
                    result=ExecutionResult(
                        success=state.status in {"PARTIAL", "FILLED"},
                        status=state.execution_status,
                        order_id=order_id,
                        ts=tick,
                        reason=state.reason,
                        filled_quantity=state.filled_quantity,
                        remaining_quantity=state.remaining_quantity,
                        avg_fill_price=state.avg_fill_price,
                        fill_price=state.avg_fill_price,
                    ),
                )
            )
        return updates

    def cancel_order(self, order_id: str, *, reason: str = CANCELED) -> None:
        self._cancel_calls.append((order_id, reason))
        tracked = self._tracked.get(order_id)
        native_order = tracked.native_order if tracked is not None else None
        if native_order is None:
            return
        api = self._api
        cancel = getattr(api, "cancel_order", None) if api is not None else None
        if callable(cancel):
            cancel(native_order)

    def close(self) -> None:
        api = self._api
        self._api = None
        if api is not None:
            close = getattr(api, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass

    def cost_fields(self, order_id: str) -> dict[str, float | None]:
        return dict(self._execution_costs.get(order_id, {}))

    def portfolio_snapshot(self) -> dict[str, object] | None:
        api = self._api
        if api is None:
            api = getattr(self.market_data, "_api", None)
            if api is not None:
                self._api = api
        if api is None and self._api_factory is not None:
            api = self._api_instance()
        if api is None:
            return None
        account = _call_optional(api, "get_account")
        positions = _call_optional(api, "get_position")
        payload: dict[str, object] = {
            "source": "tqkq_live",
            "positions_qty_by_symbol": _positions_by_symbol(positions),
        }
        cash = _first_present(account, "cash", "available", "available_funds", default=None)
        equity = _first_present(account, "equity", "balance", "account_balance", default=None)
        margin = _first_present(account, "margin_used", "margin", "frozen_margin", default=None)
        for key, value in (("cash", cash), ("equity", equity), ("margin_used", margin)):
            if isinstance(value, (int, float)):
                payload[key] = float(value)
        return payload

    def _api_instance(self) -> Any:
        if self._api is not None:
            return self._api
        shared_api = getattr(self.market_data, "_api", None)
        if shared_api is not None:
            self._api = shared_api
            return self._api
        if self._api_factory is None:
            raise ValueError("tqkq_live broker requires api_factory when dry_run=false")
        self._api = self._api_factory()
        return self._api

    def _submit_native_order(self, order: ExecutionOrder) -> Any:
        api = self._api_instance()
        insert_order = getattr(api, "insert_order", None)
        if not callable(insert_order):
            raise ValueError("tqkq_live api missing insert_order")
        return insert_order(
            symbol=order.trade_instrument_id,
            direction=_direction(order.side),
            offset=_offset(order.position_side),
            volume=order.quantity,
            limit_price=order.price,
        )

    def _wait_update(self) -> None:
        api = self._api
        wait_update = getattr(api, "wait_update", None) if api is not None else None
        if callable(wait_update):
            wait_update(deadline=None)

    def _read_native_state(self, *, order_id: str, tracked: _TrackedOrder) -> _NativeState:
        native = tracked.native_order
        api = self._api
        getter = getattr(api, "get_order", None) if api is not None else None
        if callable(getter):
            native = getter(order_id, native)
        status_raw = str(
            _first_present(
                native,
                "lifecycle_status",
                "mapped_status",
                "status",
                default="SUBMITTED",
            )
        ).upper()
        filled_raw = _float_attr(native, "filled_quantity", "volume_traded", default=0.0)
        filled = 0.0 if filled_raw is None else filled_raw
        remaining_raw = _float_attr(
            native,
            "remaining_quantity",
            "volume_left",
            default=max(0.0, tracked.order.quantity - filled),
        )
        remaining = (
            max(0.0, tracked.order.quantity - filled)
            if remaining_raw is None
            else remaining_raw
        )
        avg_price = _float_attr(native, "avg_fill_price", "trade_price", "last_price", default=None)
        if avg_price is None and filled > 0:
            avg_price = self.market_data.get_last_quote(tracked.order.instrument_id).price

        if status_raw in {"PARTIAL", "PARTIALLY_FILLED"}:
            return _NativeState(
                status="PARTIAL",
                execution_status=ExecutionStatus.PARTIALLY_FILLED,
                reason=TQKQ_LIVE_PARTIAL_FILL,
                filled_quantity=filled,
                remaining_quantity=remaining,
                avg_fill_price=avg_price,
                terminal=False,
            )
        if status_raw in {"FILLED", "FINISHED"} and remaining <= 0:
            return _NativeState(
                status="FILLED",
                execution_status=ExecutionStatus.FILLED,
                reason=TQKQ_LIVE_FILL,
                filled_quantity=tracked.order.quantity if filled <= 0 else filled,
                remaining_quantity=0.0,
                avg_fill_price=avg_price,
                terminal=True,
            )
        if status_raw in {"CANCELED", "CANCELLED"}:
            return _NativeState(
                status="CANCELED",
                execution_status=ExecutionStatus.REJECTED,
                reason=CANCELED,
                filled_quantity=filled,
                remaining_quantity=remaining,
                avg_fill_price=avg_price,
                terminal=True,
            )
        if status_raw in {"REJECTED", "ERROR"}:
            return _NativeState(
                status="REJECTED",
                execution_status=ExecutionStatus.REJECTED,
                reason=TQKQ_LIVE_REJECTED,
                filled_quantity=filled,
                remaining_quantity=remaining,
                avg_fill_price=avg_price,
                terminal=True,
            )
        if status_raw == "FINISHED" and remaining > 0:
            return _NativeState(
                status="CANCELED",
                execution_status=ExecutionStatus.REJECTED,
                reason=CANCELED,
                filled_quantity=filled,
                remaining_quantity=remaining,
                avg_fill_price=avg_price,
                terminal=True,
            )
        return _NativeState(
            status="SUBMITTED",
            execution_status=ExecutionStatus.SUBMITTED,
            reason=ORDER_SUBMITTED,
            filled_quantity=filled,
            remaining_quantity=remaining,
            avg_fill_price=avg_price,
            terminal=False,
        )

    def _record_cost(
        self,
        *,
        order_id: str,
        order: ExecutionOrder,
        filled_quantity: float,
        fill_price: float | None,
    ) -> None:
        qty = filled_quantity if filled_quantity > 0 else order.quantity
        quote = self.market_data.get_last_quote(order.instrument_id)
        cost = calculate_trade_cost(
            spec=self.instrument_specs.get(order.instrument_id),
            side=order.side,
            qty=qty,
            market_price=quote.price,
            fill_price=fill_price,
        )
        self._execution_costs[order_id] = cost.to_event_fields()

    def _reject(
        self,
        order: ExecutionOrder,
        *,
        order_id: str,
        reason: str,
    ) -> ExecutionResult:
        return ExecutionResult(
            success=False,
            status=ExecutionStatus.REJECTED,
            order_id=order_id,
            ts=self._tick,
            reason=reason,
            filled_quantity=0.0,
            remaining_quantity=order.quantity,
            avg_fill_price=None,
            fill_price=None,
        )

    def _validate_order(self, order: ExecutionOrder) -> str | None:
        trade_id = order.trade_instrument_id
        if not isinstance(trade_id, str) or not trade_id:
            return MISSING_TRADE_INSTRUMENT_ID
        if trade_id.endswith("_main"):
            return INVALID_TRADE_INSTRUMENT_ID_MAIN_ALIAS
        if _REAL_CONTRACT_RE.fullmatch(trade_id) is None:
            return INVALID_TRADE_INSTRUMENT_ID_NOT_REAL_CONTRACT
        spec = self.instrument_specs.get(order.instrument_id)
        if spec.min_qty is not None and order.quantity < spec.min_qty:
            return QUANTITY_BELOW_MIN_QTY
        return None



@dataclass(frozen=True)
class _NativeState:
    status: str
    execution_status: ExecutionStatus
    reason: str
    filled_quantity: float
    remaining_quantity: float
    avg_fill_price: float | None
    terminal: bool


def _direction(side: Side) -> str:
    if side == Side.BUY:
        return "BUY"
    if side == Side.SELL:
        return "SELL"
    raise ValueError(f"unsupported side for tqkq_live: {side}")


def _offset(position_side: PositionSide) -> str:
    if position_side in {PositionSide.LONG, PositionSide.SHORT}:
        return "OPEN"
    return "CLOSE"


def _first_present(obj: Any, *names: str, default: Any) -> Any:
    for name in names:
        if hasattr(obj, name):
            value = getattr(obj, name)
            if value is not None:
                return value
        if isinstance(obj, dict) and obj.get(name) is not None:
            return obj[name]
    return default


def _float_attr(obj: Any, *names: str, default: float | None) -> float | None:
    value = _first_present(obj, *names, default=default)
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _call_optional(obj: Any, name: str) -> Any | None:
    fn = getattr(obj, name, None)
    if not callable(fn):
        return None
    return fn()


def _positions_by_symbol(raw: Any) -> dict[str, float]:
    if raw is None:
        return {}
    items = raw.values() if isinstance(raw, dict) else raw
    out: dict[str, float] = {}
    try:
        iterator = iter(items)
    except TypeError:
        return out
    for item in iterator:
        symbol_raw = _first_present(item, "symbol", "instrument_id", default=None)
        qty_raw = _first_present(item, "quantity", "pos", "volume", default=0.0)
        if not isinstance(symbol_raw, str) or not isinstance(qty_raw, (int, float)):
            continue
        base = symbol_raw.split(".")[-1]
        if len(base) > 2 and base[-4:].isdigit():
            base = base[:-4]
        out[base] = out.get(base, 0.0) + float(qty_raw)
    return out
