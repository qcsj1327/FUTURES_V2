from __future__ import annotations

from collections.abc import Iterable

from domain.enums import Decision
from domain.signal import SignalDecision


class SignalRouter:
    def select(self, signals: Iterable[SignalDecision]) -> SignalDecision:
        signals = list(signals)

        if not signals:
            raise ValueError("no signals")

        for s in signals:
            if s.decision != Decision.HOLD:
                return s

        return signals[-1]
