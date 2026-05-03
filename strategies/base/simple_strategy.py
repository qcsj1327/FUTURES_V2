from __future__ import annotations

from adapters.marketdata.base import MarketQuote
from domain.enums import Decision, PositionSide, Side, SignalStrength
from domain.signal import SignalDecision
from strategies.base.strategy import Strategy


class StrategyEngine(Strategy):
    def generate(self, symbol: str, quote: MarketQuote) -> SignalDecision:
        # 极简策略：价格 > 100 做多，否则观望
        if quote.price > 100:
            return SignalDecision(
                decision=Decision.OPEN_LONG,
                side=Side.BUY,
                strength=SignalStrength.STRONG,
                confidence=1.0,
                reason="price_above_100",
                signal_id="auto_1",
                strategy_name="simple_trend",
                symbol=symbol,
                instrument_id=symbol,
                trade_instrument_id=None,
                runtime_id="r1",
                ts=1,
                bar_ts=1,
                bar_time="t",
                position_side=PositionSide.LONG,
            )

        return SignalDecision(
            decision=Decision.HOLD,
            side=Side.NONE,
            strength=SignalStrength.WEAK,
            confidence=0.0,
            reason="no_signal",
            signal_id="auto_0",
            strategy_name="simple_trend",
            symbol=symbol,
            instrument_id=symbol,
            trade_instrument_id=None,
            runtime_id="r1",
            ts=1,
            bar_ts=1,
            bar_time="t",
            position_side=PositionSide.FLAT,
        )
