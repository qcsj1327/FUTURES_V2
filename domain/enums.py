from __future__ import annotations

from enum import StrEnum


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"
    NONE = "none"


class Decision(StrEnum):
    OPEN_LONG = "open_long"
    OPEN_SHORT = "open_short"
    CLOSE = "close"
    HOLD = "hold"


class PositionSide(StrEnum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class SignalStrength(StrEnum):
    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"


class TriggerLifecycle(StrEnum):
    CANDIDATE = "candidate"
    CONFIRMED = "confirmed"
    TRIGGERED = "triggered"
    DUPLICATE = "duplicate"
    BLOCKED = "blocked"
    EXPIRED = "expired"


class OrderStatus(StrEnum):
    CREATED = "created"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"


class ExecutionStatus(StrEnum):
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    REJECTED = "rejected"
