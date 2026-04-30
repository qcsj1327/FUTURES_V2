from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from domain.trigger import TriggerResult


@dataclass(frozen=True)
class PortfolioAllocation:
    trigger: TriggerResult
    quantity: float | None
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class PortfolioEngine:
    def allocate(
        self,
        trigger: TriggerResult,
        default_quantity: float,
    ) -> PortfolioAllocation:
        if not trigger.triggered:
            return PortfolioAllocation(
                trigger=trigger,
                quantity=None,
                reason=trigger.reason,
                details={"source": "portfolio_engine"},
            )

        if default_quantity <= 0:
            return PortfolioAllocation(
                trigger=trigger,
                quantity=None,
                reason="invalid_quantity",
                details={"source": "portfolio_engine"},
            )

        return PortfolioAllocation(
            trigger=trigger,
            quantity=default_quantity,
            reason=trigger.reason,
            details={"source": "portfolio_engine"},
        )
