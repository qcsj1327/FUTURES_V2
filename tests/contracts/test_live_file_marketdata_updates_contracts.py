from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from app.orchestration.session_builder import build_universe_session
from config.defaults import default_plan


def test_live_file_marketdata_updates(tmp_path: Path) -> None:
    rid = "rt_livefile"

    prices = tmp_path / "prices.json"
    prices.write_text(
        json.dumps({"au": {"price": 100.0, "volume": 10.0, "ts": 1}}, ensure_ascii=False),
        encoding="utf-8",
    )

    plan = default_plan(runtime_id=rid)

    ds = plan.datastore
    ds = replace(ds, store_root=tmp_path / "data" / "store")
    plan = replace(plan, datastore=ds)

    md = plan.adapters.market_data
    md = replace(md, mode="live_file", prices_path=str(prices))
    plan = replace(plan, adapters=replace(plan.adapters, market_data=md))

    session = build_universe_session(plan=plan, env="live", runtime_id=rid)

    q0 = session.market_data.get_last_quote("au")

    prices.write_text(
        json.dumps({"au": {"price": 123.0, "volume": 12.0, "ts": 2}}, ensure_ascii=False),
        encoding="utf-8",
    )
    q1 = session.market_data.get_last_quote("au")

    assert q0.price != q1.price
    assert q1.price == 123.0
    assert q1.volume == 12.0
    assert q1.ts == 2
