from __future__ import annotations

from domain.enums import TriggerLifecycle
from domain.signal import SignalDecision
from domain.trigger import TriggerResult


class TriggerEngine:
    def process(self, decision: SignalDecision, runtime_id: str) -> TriggerResult:
        return TriggerResult(
            decision=decision.decision,
            side=decision.side,
            lifecycle=TriggerLifecycle.TRIGGERED,
            triggered=True,
            runtime_id=runtime_id,
            signal_id=decision.signal_id,
            strategy_name=decision.strategy_name,
            symbol=decision.symbol,
            instrument_id=decision.instrument_id,
            trade_instrument_id=decision.trade_instrument_id,
            ts=decision.ts,
            bar_ts=decision.bar_ts,
            bar_time=decision.bar_time,
            position_side=decision.position_side,
            confidence=decision.confidence,
            strength=decision.strength,
            reason=decision.reason,
        )
