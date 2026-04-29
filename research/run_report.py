from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RunReport:
    cycles_run: int
    orders_submitted: int
    final_position_qty: float
    notes: list[str] = field(default_factory=list)
