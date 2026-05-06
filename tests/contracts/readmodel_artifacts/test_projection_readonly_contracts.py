from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from web.readmodel.dashboard_projection import build_dashboard_projection


def _build_with_lifecycle(event: dict[str, Any]) -> dict[str, Any]:
    empty: dict[str, list[dict[str, Any]]] = {"local": [], "dryrun": [], "live": []}
    return build_dashboard_projection(
        runtime_id="rt_projection_readonly",
        plan_cfg={"runtime": {"mode": "live"}, "universe": {"symbols": ["au"]}},
        execution={},
        portfolio={"local": None, "dryrun": None, "live": {}},
        latest_portfolios={"local": None, "dryrun": None, "live": None},
        event_stats={"local": {}, "dryrun": {}, "live": {}},
        lifecycle_events={**empty, "live": [event]},
        order_events=empty,
        fill_events=empty,
        rank_events=empty,
        strategy_score_events=empty,
        lifecycle_stats={"local": {}, "dryrun": {}, "live": {}},
        risk_stats={"local": {}, "dryrun": {}, "live": {}},
        top_lifecycle_reject_reasons={"local": [], "dryrun": [], "live": []},
        strategy_switch_proposal=None,
        strategy_switch_approved=None,
        strategy_switch_rejected=None,
        enabled_strategies_by_symbol={"local": {}, "dryrun": {}, "live": {}},
        warning_codes=[],
    )


def test_projection_does_not_modify_event_envelope_or_source_row() -> None:
    event = {
        "event_id": "evt-1",
        "runtime_profile": "live",
        "datastore_scope": "live",
        "source": "runtime",
        "payload_type": "order_lifecycle",
        "order_id": "o1",
        "status": "SUBMITTED",
        "symbol": "au",
        "quantity": 1.0,
        "ts": 1,
    }
    before = deepcopy(event)

    projection = _build_with_lifecycle(event)

    assert event == before
    assert projection["lifecycle_view"]["live"]["items"][0]["source_event_id"] == "evt-1"


def test_web_readmodel_does_not_import_state_mutation_paths() -> None:
    for path in Path("web/readmodel").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "StateEngine" not in source
        assert "append_order_event" not in source
        assert "append_fill_event" not in source
        assert "append_lifecycle_event" not in source
        assert "PortfolioState(" not in source


def test_web_projection_does_not_write_trading_events() -> None:
    for root in (Path("web/readmodel"), Path("web/viewmodels"), Path("web/api")):
        for path in root.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "append_order_event" not in source
            assert "append_fill_event" not in source
            assert "write_order_event" not in source
            assert "write_fill_event" not in source
            assert "state_engine.apply" not in source


def test_projection_code_does_not_create_raw_trading_artifacts() -> None:
    for root in (Path("web/readmodel"), Path("web/viewmodels"), Path("web/api")):
        for path in root.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert '"artifact_type": "raw_trading_event"' not in source
            assert '"artifact_type": "trading_event"' not in source
