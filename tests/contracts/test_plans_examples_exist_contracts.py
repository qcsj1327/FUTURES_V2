from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    # .../futures_v2/tests/contracts/<file>.py -> parents:
    # 0=contracts, 1=tests, 2=repo root
    return Path(__file__).resolve().parents[2]


def test_plans_examples_exist() -> None:
    root = _repo_root()
    assert (root / "plans" / "dev.simulated_v2.json").exists()
    assert (root / "plans" / "dev.live_file.json").exists()
    assert (root / "plans" / "dev.mode_simulated_v2.json").exists()
    assert (root / "plans" / "dev.mode_live_file.json").exists()
    assert (root / "plans" / "dev.mode_tqkq_sim.json").exists()
    assert (root / "plans" / "dev.strategy_switch.json").exists()
    assert (root / "plans" / "dev.order_lifecycle_v2.json").exists()
    assert (root / "plans" / "dev.risk_pending_guard.json").exists()
    assert (root / "plans" / "dev.tqkq_sim_expire.json").exists()
    assert (root / "plans" / "dev.tqkq_live_dryrun.json").exists()
    assert (root / "plans" / "dev.topn_switch_calendar_v2.json").exists()
    assert (root / "plans" / "dev.topn_switch_calendar.json").exists()
    assert (root / "plans" / "dev.portfolio_risk_v1.json").exists()
