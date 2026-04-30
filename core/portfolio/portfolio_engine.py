from __future__ import annotations

from domain.signal import SignalDecision


class PortfolioEngine:
    def allocate(self, decision: SignalDecision) -> SignalDecision:
        return decision
