from __future__ import annotations

import inspect

from core.services.audit.service import AuditService


class _Portfolio:
    metadata = {"cash": 1000.0, "equity": 1200.0, "margin_used": 20.0}
    positions: dict[str, object] = {}


def test_audit_service_does_not_depend_on_state_mutation_api() -> None:
    source = inspect.getsource(AuditService)

    assert "StateEngine" not in source
    assert "apply_order_event" not in source
    assert "apply_fill_event" not in source
    assert "OrderEvent(" not in source
    assert "FillEvent(" not in source
    assert "append_order_event" not in source
    assert "append_fill_event" not in source
    assert "save_portfolio_snapshot" not in source


def test_audit_report_is_observation_only() -> None:
    report = AuditService().collect(
        runtime_id="rt_live",
        runtime_profile="live",
        datastore_scope="live",
        portfolio_snapshot=_Portfolio(),
        broker_snapshot={"cash": 1000.0, "equity": 1200.0, "margin_used": 20.0},
        generated_at="2026-05-09T00:00:00+00:00",
    )

    payload = report.to_dict()
    assert payload["is_source_of_truth"] is False
    assert payload["mutation_allowed"] is False
    assert payload["diagnostic_only"] is False
    assert all(item["is_source_of_truth"] is False for item in payload["observations"])
    assert all(item["mutation_allowed"] is False for item in payload["observations"])


def test_critical_alert_only_suggests_action() -> None:
    report = AuditService().collect(
        runtime_id="rt_live",
        runtime_profile="live",
        datastore_scope="live",
        portfolio_snapshot=_Portfolio(),
        broker_snapshot={"cash": 0.0, "equity": 0.0, "margin_used": 20.0},
        generated_at="2026-05-09T00:00:00+00:00",
    )

    assert report.alerts
    assert {alert.suggested_action for alert in report.alerts} == {"suspend_new_trading"}
    assert all(alert.mutation_allowed is False for alert in report.alerts)
    assert all(alert.is_source_of_truth is False for alert in report.alerts)
