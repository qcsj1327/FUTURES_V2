from __future__ import annotations

from domain.enums import Decision, Side, TriggerLifecycle
from domain.signal import SignalDecision
from domain.trigger import TriggerResult


class TriggerEngine:
    def process(self, decision: SignalDecision, runtime_id: str) -> TriggerResult:
        reason = self._blocked_reason(decision)

        if reason is not None:
            return TriggerResult(
                decision=decision.decision,
                side=decision.side,
                lifecycle=TriggerLifecycle.BLOCKED,
                triggered=False,
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
                reason=reason,
                details={
                    "source": "trigger_engine",
                    "stop_loss": decision.stop_loss,
                    "take_profit": decision.take_profit,
                },
            )

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
            details={
                "source": "trigger_engine",
                "stop_loss": decision.stop_loss,
                "take_profit": decision.take_profit,
            },
        )

    def _blocked_reason(self, decision: SignalDecision) -> str | None:
        if decision.instrument_id is None:
            return "missing_instrument_id"

        if decision.trade_instrument_id is None:
            return "missing_trade_instrument_id"

        if decision.decision == Decision.HOLD and decision.side != Side.NONE:
            return "hold_with_directional_side"

        return None
