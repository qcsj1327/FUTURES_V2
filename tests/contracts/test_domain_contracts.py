from __future__ import annotations

from dataclasses import fields, is_dataclass
from typing import Any

from domain import enums
from domain.event import FillEvent, OrderEvent
from domain.execution import ExecutionOrder, ExecutionResult
from domain.feature import FeatureSnapshot
from domain.market import MarketContext
from domain.performance import ClosedTrade, PerformanceSnapshot
from domain.risk import RiskDecision
from domain.signal import SignalCandidate, SignalDecision
from domain.state import OrderState, PositionState, StateSnapshot, StrategyState, SystemState
from domain.trigger import TriggerResult


def field_names(cls: type[Any]) -> set[str]:
    return {field.name for field in fields(cls)}


def assert_dataclass(cls: type[Any]) -> None:
    assert is_dataclass(cls), f"{cls} must be dataclass"


def test_enums() -> None:
    assert enums.Side.BUY.value == "buy"
    assert enums.Side.SELL.value == "sell"
    assert enums.Side.NONE.value == "none"

    assert enums.Decision.OPEN_LONG.value == "open_long"
    assert enums.Decision.OPEN_SHORT.value == "open_short"
    assert enums.Decision.CLOSE.value == "close"
    assert enums.Decision.HOLD.value == "hold"

    assert enums.PositionSide.LONG.value == "long"
    assert enums.PositionSide.SHORT.value == "short"
    assert enums.PositionSide.FLAT.value == "flat"

    assert enums.ExecutionStatus.SUBMITTED.value == "submitted"
    assert enums.ExecutionStatus.PARTIALLY_FILLED.value == "partially_filled"
    assert enums.ExecutionStatus.FILLED.value == "filled"
    assert enums.ExecutionStatus.REJECTED.value == "rejected"


def test_feature_snapshot_fields() -> None:
    assert_dataclass(FeatureSnapshot)
    assert field_names(FeatureSnapshot) == {
        "ts",
        "bar_ts",
        "bar_time",
        "timeframe",
        "returns",
        "bar_return",
        "range",
        "price_range",
        "atr",
        "volume_ratio",
        "breakout_level",
        "moving_average",
        "bias",
    }


def test_market_context_fields() -> None:
    assert_dataclass(MarketContext)
    assert field_names(MarketContext) == {
        "symbol",
        "instrument_id",
        "trade_instrument_id",
        "ts",
        "bar_ts",
        "bar_time",
        "timeframe",
        "trading_date",
        "market_phase",
        "market_mode",
        "is_trading_time",
        "last_price",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "feature_snapshot",
        "raw",
    }


def test_signal_candidate_fields() -> None:
    assert_dataclass(SignalCandidate)
    assert field_names(SignalCandidate) == {
        "signal_id",
        "strategy_name",
        "symbol",
        "instrument_id",
        "trade_instrument_id",
        "ts",
        "bar_ts",
        "bar_time",
        "decision",
        "side",
        "position_side",
        "confidence",
        "strength",
        "reason",
        "expected_price",
        "stop_loss",
        "take_profit",
        "holding_period_hint",
        "tags",
        "features_ref",
        "raw",
    }


def test_signal_decision_fields() -> None:
    assert_dataclass(SignalDecision)
    assert field_names(SignalDecision) == {
        "decision",
        "side",
        "strength",
        "confidence",
        "reason",
        "signal_id",
        "strategy_name",
        "symbol",
        "instrument_id",
        "trade_instrument_id",
        "runtime_id",
        "ts",
        "bar_ts",
        "bar_time",
        "position_side",
        "expected_price",
        "stop_loss",
        "take_profit",
        "tags",
        "raw",
    }


def test_trigger_result_fields() -> None:
    assert_dataclass(TriggerResult)
    assert field_names(TriggerResult) == {
        "decision",
        "side",
        "lifecycle",
        "triggered",
        "runtime_id",
        "bar_ts",
        "signal_id",
        "strategy_name",
        "symbol",
        "instrument_id",
        "trade_instrument_id",
        "ts",
        "bar_time",
        "position_side",
        "confidence",
        "strength",
        "reason",
        "details",
    }


def test_risk_decision_fields() -> None:
    assert_dataclass(RiskDecision)
    assert field_names(RiskDecision) == {
        "instrument_id",
        "trade_instrument_id",
        "allowed",
        "decision",
        "side",
        "position_side",
        "lifecycle",
        "quantity",
        "stop_loss",
        "take_profit",
        "risk_budget",
        "reason",
        "details",
    }


def test_execution_fields() -> None:
    assert_dataclass(ExecutionOrder)
    assert_dataclass(ExecutionResult)

    assert field_names(ExecutionOrder) == {
        "instrument_id",
        "side",
        "position_side",
        "quantity",
        "order_type",
        "trade_instrument_id",
        "price",
        "stop_loss",
        "take_profit",
        "client_order_id",
    }

    assert field_names(ExecutionResult) == {
        "success",
        "status",
        "order_id",
        "ts",
        "fill_price",
        "reason",
        "filled_quantity",
        "remaining_quantity",
        "avg_fill_price",
    }


def test_event_fields() -> None:
    assert_dataclass(OrderEvent)
    assert_dataclass(FillEvent)

    assert field_names(OrderEvent) == {
        "strategy_name",
        "instrument_id",
        "trade_instrument_id",
        "order_id",
        "side",
        "position_side",
        "quantity",
        "status",
        "ts",
        "reason",
        "client_order_id",
        "runtime_id",
        "metadata",
    }

    assert field_names(FillEvent) == {
        "strategy_name",
        "instrument_id",
        "trade_instrument_id",
        "order_id",
        "side",
        "position_side",
        "quantity",
        "fill_price",
        "ts",
        "fill_id",
        "client_order_id",
        "runtime_id",
        "metadata",
    }


def test_state_fields() -> None:
    assert_dataclass(OrderState)
    assert_dataclass(PositionState)
    assert_dataclass(StrategyState)
    assert_dataclass(SystemState)
    assert_dataclass(StateSnapshot)

    assert "order_id" in field_names(OrderState)
    assert "position_side" in field_names(PositionState)
    assert "last_signal_id" in field_names(StrategyState)
    assert "is_running" in field_names(SystemState)
    assert "pnl" in field_names(StateSnapshot)


def test_performance_fields() -> None:
    assert_dataclass(PerformanceSnapshot)
    assert_dataclass(ClosedTrade)

    assert "net_profit" in field_names(PerformanceSnapshot)
    assert "entry_price" in field_names(ClosedTrade)
