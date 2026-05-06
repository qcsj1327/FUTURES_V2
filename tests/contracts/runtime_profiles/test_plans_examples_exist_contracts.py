from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    # .../futures_v2/tests/contracts/<file>.py -> parents:
    # 0=contracts, 1=tests, 2=repo root
    return Path(__file__).resolve().parents[3]


def test_plans_examples_exist() -> None:
    root = _repo_root()
    assert (root / "plans" / "dev.local.json").exists()
    assert (root / "plans" / "dev.dryrun.json").exists()
    assert (root / "plans" / "dev.live.json").exists()
    assert (root / "plans" / "prices.json").exists()
    assert (root / "plans" / "README.md").exists()
