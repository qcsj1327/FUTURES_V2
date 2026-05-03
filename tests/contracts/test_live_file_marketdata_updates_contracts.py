from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from app.orchestration.session_builder import build_universe_session
from config.defaults import default_plan


def test_live_file_marketdata_updates(tmp_path: Path) -> None:
    rid = "rt_livefile"

    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps({"au": 100.0}, ensure_ascii=False), encoding="utf-8")

    plan = default_plan(runtime_id=rid)

    # datastore under tmp_path
    ds = plan.datastore
    ds = replace(ds, store_root=tmp_path / "data" / "store")
    plan = replace(plan, datastore=ds)

    # switch adapter to live_file
    md = plan.adapters.market_data
    md = replace(md, mode="live_file", prices_path=str(prices))
    plan = replace(plan, adapters=replace(plan.adapters, market_data=md))

    session = build_universe_session(plan=plan, env="live", runtime_id=rid)

    p0 = session.market_data.get_last_price("au")

    prices.write_text(json.dumps({"au": 123.0}, ensure_ascii=False), encoding="utf-8")
    p1 = session.market_data.get_last_price("au")

    assert p0 != p1
    assert p1 == 123.0
