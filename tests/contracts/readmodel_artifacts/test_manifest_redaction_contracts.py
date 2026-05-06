from __future__ import annotations

import json
from pathlib import Path

from optimize.promoter.manifest_artifact import (
    redact_manifest_value,
    redacted_effective_plan_summary,
    write_promotion_manifest,
)

SECRET_TOKEN = "rt_live_confirm_secret"
SECRET_PASSWORD = "broker-password"
PRIVATE_PLAN_PATH = "/Users/Yanzl/private/plans/dev.live.json"
PRIVATE_PRICES_PATH = "/Users/Yanzl/private/prices.json"


def _plan() -> dict[str, object]:
    return {
        "runtime": {
            "mode": "live",
            "runtime_id": "rt_live",
            "active_top_n": 3,
            "unrelated_full_config_field": "must_not_survive",
        },
        "datastore": {
            "store_root": "/Users/Yanzl/private/store",
            "artifacts_root": "/Users/Yanzl/private/artifacts",
        },
        "universe": {"symbols": ["au", "rb"]},
        "instruments": {
            "trading_sessions": {
                "au": [{"start": "09:00", "end": "10:15"}],
                "rb": [{"start": "21:00", "end": "23:00"}],
            },
            "roll_policy": {
                "mode": "fixed_contract",
                "contracts": {"au": "SHFE.au2606", "rb": "SHFE.rb2610"},
                "resolve_from_market_data": False,
                "close_on_roll": False,
                "cooldown_ticks": 0,
            },
            "spec_source": "static",
        },
        "router": {"mode": "priority", "tie_breaker": "confidence"},
        "strategies": [
            {
                "name": "simple_strategy",
                "symbols": ["au"],
                "priority": 1,
                "weight": 1.0,
                "params": {"secret": "strategy-secret"},
            }
        ],
        "promotion": {"write_manifest": True, "write_approved": True},
        "strategy_switch": {
            "enabled_by_symbol": {"au": ["simple_strategy"]},
            "approval_required": False,
        },
        "adapters": {
            "market_data": {
                "mode": "local_file",
                "prices_path": PRIVATE_PRICES_PATH,
                "params": {"environment": "TQKQ_PASS=raw-env"},
            },
            "broker": {
                "mode": "tqkq",
                "params": {
                    "submit_mode": "live",
                    "confirm_live": True,
                    "confirm_live_token": SECRET_TOKEN,
                    "password": SECRET_PASSWORD,
                    "broker_credential": "raw-credential",
                },
            },
        },
    }


def test_manifest_omits_full_plan_config_and_redacts_sensitive_values(
    tmp_path: Path,
) -> None:
    path = write_promotion_manifest(
        runtime_id="rt_live",
        candidate_id="cand_live",
        candidate_config={"runtime_profile": "live", "datastore_scope": "live"},
        thresholds={"min_events": 1},
        current_summary_path=None,
        candidate_summary_path=None,
        decision_path=None,
        approved_path=None,
        plan=_plan(),
        plan_path=PRIVATE_PLAN_PATH,
        plan_sha256="sha256-plan",
        output_dir=tmp_path,
        filename="manifest.json",
        runtime_profile="live",
        datastore_scope="live",
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    plan = payload["plan"]

    assert "config" not in plan
    assert plan["path"] == "<redacted>/dev.live.json"
    assert plan["sha256"] == "sha256-plan"
    assert "effective_config_summary" in plan
    assert plan["redaction_status"]["redacted"] is True
    assert SECRET_TOKEN not in rendered
    assert SECRET_PASSWORD not in rendered
    assert "raw-credential" not in rendered
    assert "TQKQ_PASS=raw-env" not in rendered
    assert PRIVATE_PLAN_PATH not in rendered
    assert PRIVATE_PRICES_PATH not in rendered
    assert "unrelated_full_config_field" not in rendered


def test_redaction_helper_recurses_nested_dicts_and_lists() -> None:
    redacted = redact_manifest_value(
        {
            "outer": [
                {
                    "confirm_live_token": SECRET_TOKEN,
                    "password": SECRET_PASSWORD,
                    "nested": {"secret": "deep-secret"},
                }
            ]
        }
    )

    rendered = json.dumps(redacted, ensure_ascii=False, sort_keys=True)

    assert SECRET_TOKEN not in rendered
    assert SECRET_PASSWORD not in rendered
    assert "deep-secret" not in rendered


def test_effective_plan_summary_is_allowlisted_and_path_safe() -> None:
    summary = redacted_effective_plan_summary(_plan())
    rendered = json.dumps(summary, ensure_ascii=False, sort_keys=True)

    assert summary["runtime_profile"] == "live"
    assert summary["datastore_scope"] == "live"
    assert summary["universe"]["symbols"] == ["au", "rb"]
    assert summary["instruments"]["roll_policy"]["contracts"] == {
        "au": "SHFE.au2606",
        "rb": "SHFE.rb2610",
    }
    assert summary["instruments"]["trading_sessions"]["au"] == [
        {"start": "09:00", "end": "10:15"}
    ]
    assert "<redacted>/prices.json" in rendered
    assert PRIVATE_PRICES_PATH not in rendered
    assert SECRET_TOKEN not in rendered
    assert "strategy-secret" not in rendered
