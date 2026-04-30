from __future__ import annotations

from core.portfolio.portfolio_engine import PortfolioEngine
from domain.enums import Decision, PositionSide, Side, SignalStrength
from domain.signal import SignalDecision


def test_portfolio_engine_passes_signal_decision() -> None:
    decision = SignalDecision(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        strength=SignalStrength.STRONG,
        confidence=1.0,
        reason="portfolio",
        signal_id="s1",
        strategy_name="test",
        symbol="au",
        instrument_id="au",
        trade_instrument_id="au_main",
        runtime_id="r1",
        ts=1,
        bar_ts=1,
        bar_time="t",
        position_side=PositionSide.LONG,
    )

    result = PortfolioEngine().allocate(decision)

    assert result is decision
