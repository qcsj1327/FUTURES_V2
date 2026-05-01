from __future__ import annotations

from pathlib import Path

from app.runtime import Runtime
from core.services.trade.exit_order_factory import ExitOrderFactory
from core.services.trade.exit_rules import ExitRules
from core.services.trade.exit_service import ExitService
from core.state.state_engine import StateEngine


def test_exit_modules_live_under_trade_service() -> None:
    assert Path("core/services/trade/exit_rules.py").exists()
    assert Path("core/services/trade/exit_order_factory.py").exists()
    assert Path("core/services/trade/exit_service.py").exists()


def test_exit_modules_do_not_live_under_state() -> None:
    assert not Path("core/state/exit_rules.py").exists()
    assert not Path("core/state/exit_order_factory.py").exists()


def test_state_engine_does_not_own_exit_orchestration() -> None:
    state = StateEngine()

    assert not hasattr(state, "create_exit_order")
    assert not hasattr(state, "exit_rules")
    assert not hasattr(state, "exit_order_factory")


def test_runtime_owns_exit_service() -> None:
    runtime = Runtime()

    assert isinstance(runtime.exit_service, ExitService)


def test_exit_service_owns_exit_rules_and_order_factory() -> None:
    service = ExitService()

    assert isinstance(service.exit_rules, ExitRules)
    assert isinstance(service.exit_order_factory, ExitOrderFactory)
