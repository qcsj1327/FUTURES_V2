from __future__ import annotations

from core.execution.lifecycle_reasons import (
    ALLOWED_LIFECYCLE_REASONS,
    RISK_MAX_MARGIN_USED,
    RISK_MAX_NOTIONAL,
    RISK_MAX_RISK_RATIO,
)


def test_risk_promotion_v2_risk_reasons_allowlist_contract() -> None:
    assert RISK_MAX_RISK_RATIO in ALLOWED_LIFECYCLE_REASONS
    assert RISK_MAX_NOTIONAL in ALLOWED_LIFECYCLE_REASONS
    assert RISK_MAX_MARGIN_USED in ALLOWED_LIFECYCLE_REASONS
