from __future__ import annotations

from collections.abc import Iterable

from domain.enums import Decision
from domain.signal import SignalDecision


class SignalRouter:
    def select(self, signals: Iterable[SignalDecision]) -> SignalDecision:
        for s in signals:
            if s.decision != Decision.HOLD:
                return s

        # fallback：返回最后一个（通常是 HOLD）
        return list(signals)[-1]
