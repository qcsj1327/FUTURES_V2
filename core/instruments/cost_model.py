from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from core.instruments.specs import InstrumentSpec
from domain.enums import Side


@dataclass(frozen=True)
class CostBreakdown:
    market_price: float
    raw_fill_price: float
    fill_price: float
    quantity: float
    multiplier: float
    tick_size: float
    notional: float
    commission: float
    slippage: float
    cost_total: float
    margin: float | None

    def to_event_fields(self) -> dict[str, float | None]:
        return asdict(self)


def calculate_trade_cost(
    *,
    spec: InstrumentSpec,
    side: Side,
    qty: float,
    market_price: float,
    fill_price: float | None = None,
) -> CostBreakdown:
    raw_fill = (
        fill_price
        if fill_price is not None
        else _slipped_price(spec=spec, side=side, price=market_price)
    )
    aligned_fill = align_price_to_tick(price=raw_fill, tick_size=spec.tick_size, side=side)
    notional = aligned_fill * qty * spec.multiplier
    commission = _commission(spec=spec, qty=qty, notional=notional)
    slippage = abs(aligned_fill - market_price) * qty * spec.multiplier
    margin = notional * spec.margin_rate if spec.margin_rate is not None else None
    return CostBreakdown(
        market_price=market_price,
        raw_fill_price=raw_fill,
        fill_price=aligned_fill,
        quantity=qty,
        multiplier=spec.multiplier,
        tick_size=spec.tick_size,
        notional=notional,
        commission=commission,
        slippage=slippage,
        cost_total=commission + slippage,
        margin=margin,
    )


def align_price_to_tick(*, price: float, tick_size: float, side: Side) -> float:
    if tick_size <= 0:
        raise ValueError("tick_size must be > 0")
    price_d = Decimal(str(price))
    tick_d = Decimal(str(tick_size))
    rounding = ROUND_CEILING if side == Side.BUY else ROUND_FLOOR
    ticks = (price_d / tick_d).to_integral_value(rounding=rounding)
    return float(ticks * tick_d)


def _slipped_price(*, spec: InstrumentSpec, side: Side, price: float) -> float:
    sign = 1.0 if side == Side.BUY else -1.0
    model = spec.slippage_model
    if model.mode == "bps":
        return price * (1.0 + sign * model.value / 10_000.0)
    if model.mode == "ticks":
        return price + sign * model.value * spec.tick_size
    raise ValueError(f"invalid slippage model: {model.mode}")


def _commission(*, spec: InstrumentSpec, qty: float, notional: float) -> float:
    model = spec.commission_model
    if model.mode == "fixed_per_order":
        return model.value
    if model.mode == "per_qty":
        return model.value * qty
    if model.mode == "bps_notional":
        return notional * model.value / 10_000.0
    raise ValueError(f"invalid commission model: {model.mode}")
