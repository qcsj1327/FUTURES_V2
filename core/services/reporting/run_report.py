from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RunReport:
    cycles_run: int
    orders_submitted: int
    final_position_qty: float
    notes: list[str] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    cash_curve: list[float] = field(default_factory=list)
    position_qty_curve: list[float] = field(default_factory=list)
    max_drawdown: float = 0.0
