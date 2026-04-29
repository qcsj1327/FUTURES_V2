from __future__ import annotations

from research.run_report import RunReport


class ReportAnalyzer:
    def rank_by_orders(self, reports: dict[str, RunReport]) -> list[tuple[str, RunReport]]:
        return sorted(
            reports.items(),
            key=lambda item: item[1].orders_submitted,
            reverse=True,
        )

    def rank_by_position(self, reports: dict[str, RunReport]) -> list[tuple[str, RunReport]]:
        return sorted(
            reports.items(),
            key=lambda item: item[1].final_position_qty,
            reverse=True,
        )
