from __future__ import annotations

from collections.abc import Mapping

from core.portfolio.portfolio_metrics import PortfolioMetrics


def build_portfolio_metrics_observation(
    *,
    metrics: PortfolioMetrics,
    max_risk_ratio_seen: float,
    broker_portfolio_sync: Mapping[str, object] | None = None,
) -> dict[str, object]:
    snapshot = metrics.as_metadata()
    snapshot["max_risk_ratio_seen"] = max_risk_ratio_seen
    snapshot["source"] = "runtime_observation"
    snapshot["state_source_of_truth"] = False
    if broker_portfolio_sync:
        snapshot["broker_portfolio_sync_observation"] = dict(broker_portfolio_sync)
    return snapshot
