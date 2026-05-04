from __future__ import annotations

from pathlib import Path

import pytest

from scripts.run_plan import main as run_plan_main
from tools.inspect_run import inspect_run


def test_portfolio_risk_v1_metrics_include_equity_margin_and_ratio(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = Path(__file__).resolve().parents[2] / "plans" / "dev.portfolio_risk_v1.json"
    rid = "rt_portfolio_risk_v1_metrics"

    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid, "--clean"]) == 0
    report = inspect_run(
        runtime_id=rid,
        store_root=tmp_path / "data" / "store",
        artifacts_root=tmp_path / "data" / "artifacts",
        tail=40,
    )

    portfolio = report["portfolio"]["live"]
    assert isinstance(portfolio, dict)
    equity = portfolio["equity"]
    margin_used = portfolio["margin_used"]
    risk_ratio = portfolio["risk_ratio"]
    cash = portfolio["cash"]
    assert isinstance(equity, float) and equity > 0
    assert isinstance(margin_used, float) and margin_used > 0
    assert isinstance(risk_ratio, float)
    assert isinstance(cash, float)
    assert risk_ratio == pytest.approx(margin_used / equity)
    assert cash == pytest.approx(equity - margin_used)
