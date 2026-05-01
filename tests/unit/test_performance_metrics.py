from __future__ import annotations

from research.performance import PerformanceAnalyzer, PerformanceMetrics


def test_performance_empty_curve_returns_zero_metrics() -> None:
    metrics = PerformanceAnalyzer().analyze([])

    assert metrics == PerformanceMetrics(
        total_return=0.0,
        max_drawdown=0.0,
        volatility=0.0,
        sharpe_ratio=None,
    )


def test_performance_total_return() -> None:
    metrics = PerformanceAnalyzer().analyze([100.0, 110.0, 120.0])

    assert metrics.total_return == 0.2


def test_performance_max_drawdown() -> None:
    metrics = PerformanceAnalyzer().analyze([100.0, 120.0, 90.0, 110.0])

    assert metrics.max_drawdown == 0.25


def test_performance_volatility_is_non_negative() -> None:
    metrics = PerformanceAnalyzer().analyze([100.0, 105.0, 103.0, 110.0])

    assert metrics.volatility >= 0.0


def test_performance_sharpe_is_none_when_no_volatility() -> None:
    metrics = PerformanceAnalyzer().analyze([100.0, 100.0, 100.0])

    assert metrics.sharpe_ratio is None


def test_performance_sharpe_exists_when_returns_vary() -> None:
    metrics = PerformanceAnalyzer().analyze([100.0, 110.0, 105.0, 120.0])

    assert metrics.sharpe_ratio is not None
