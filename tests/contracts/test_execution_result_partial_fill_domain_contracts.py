from __future__ import annotations

from domain.enums import ExecutionStatus
from domain.execution import ExecutionResult


def test_execution_status_supports_fill_lifecycle() -> None:
    assert ExecutionStatus.SUBMITTED.value == "submitted"
    assert ExecutionStatus.PARTIALLY_FILLED.value == "partially_filled"
    assert ExecutionStatus.FILLED.value == "filled"
    assert ExecutionStatus.REJECTED.value == "rejected"


def test_execution_result_supports_partial_fill_fields() -> None:
    result = ExecutionResult(
        success=True,
        status=ExecutionStatus.PARTIALLY_FILLED,
        order_id="o1",
        ts=1,
        fill_price=100.0,
        filled_quantity=2.0,
        remaining_quantity=3.0,
        avg_fill_price=100.0,
        reason="partial_fill",
    )

    assert result.filled_quantity == 2.0
    assert result.remaining_quantity == 3.0
    assert result.avg_fill_price == 100.0


def test_execution_result_partial_fill_fields_default_to_none() -> None:
    result = ExecutionResult(
        success=False,
        status=ExecutionStatus.REJECTED,
        reason="rejected",
    )

    assert result.filled_quantity is None
    assert result.remaining_quantity is None
    assert result.avg_fill_price is None
