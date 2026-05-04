from __future__ import annotations

from pathlib import Path

import pytest

from scripts.run_plan import main as run_plan_main
from tools.inspect_run import inspect_run


def test_portfolio_metrics_v2_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = Path(__file__).resolve().parents[2] / "plans" / "dev.portfolio_risk_v2.json"
    rid = "rt_portfolio_metrics_v2"

    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid, "--clean"]) == 0

    report = inspect_run(runtime_id=rid, tail=20)
    portfolio = report["portfolio"]["live"]
    assert isinstance(portfolio, dict)
    for key in (
        "equity",
        "cash",
        "margin_used",
        "risk_ratio",
        "unrealized_pnl",
        "realized_pnl",
        "notional_by_symbol",
        "margin_by_symbol",
    ):
        assert key in portfolio
    equity = portfolio["equity"]
    margin_used = portfolio["margin_used"]
    risk_ratio = portfolio["risk_ratio"]
    assert isinstance(equity, float)
    assert isinstance(margin_used, float)
    assert isinstance(risk_ratio, float)
    assert risk_ratio == pytest.approx(margin_used / equity)
    assert isinstance(portfolio["margin_by_symbol"], dict)
    assert portfolio["margin_by_symbol"]
