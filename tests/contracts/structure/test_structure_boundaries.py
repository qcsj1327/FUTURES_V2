from __future__ import annotations

import ast
import re
from pathlib import Path

from app.runtime_factory import RuntimeFactory
from core.services.trade.exit_order_factory import ExitOrderFactory
from core.services.trade.exit_rules import ExitRules
from core.services.trade.exit_service import ExitService
from core.state.state_engine import StateEngine


def _python_files(root: str) -> list[Path]:
    return sorted(Path(root).rglob("*.py"))


def _imports_from(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def _has_forbidden_import(path: Path, prefixes: tuple[str, ...]) -> bool:
    return any(
        module == prefix or module.startswith(prefix + ".")
        for module in _imports_from(path)
        for prefix in prefixes
    )


def test_domain_stays_contract_only() -> None:
    forbidden = ("adapters", "app", "config", "core", "research", "tools", "web")
    offenders = [
        str(path)
        for path in _python_files("domain")
        if _has_forbidden_import(path, forbidden)
    ]

    assert offenders == []


def test_core_does_not_depend_on_adapters_or_io() -> None:
    forbidden_imports = ("adapters", "app", "config", "research", "tools", "web")
    import_offenders = [
        str(path)
        for path in _python_files("core")
        if _has_forbidden_import(path, forbidden_imports)
    ]
    io_patterns = (
        r"\bopen\(",
        r"\.read_text\(",
        r"\.write_text\(",
        r"json\.dump",
        r"json\.dumps",
    )
    io_offenders = [
        str(path)
        for path in _python_files("core")
        if any(re.search(pattern, path.read_text(encoding="utf-8")) for pattern in io_patterns)
    ]

    assert import_offenders == []
    assert io_offenders == []


def test_strategies_do_not_reach_runtime_broker_state_or_io() -> None:
    forbidden_imports = ("adapters", "app", "core.state", "core.execution")
    import_offenders = [
        str(path)
        for path in _python_files("strategies")
        if _has_forbidden_import(path, forbidden_imports)
    ]
    io_tokens = ("open(", ".read_text(", ".write_text(", "requests", "tqsdk")
    io_offenders = [
        str(path)
        for path in _python_files("strategies")
        if any(token in path.read_text(encoding="utf-8") for token in io_tokens)
    ]

    assert import_offenders == []
    assert io_offenders == []


def test_orchestration_does_not_depend_on_research_for_runtime_artifacts() -> None:
    offenders = [
        str(path)
        for path in _python_files("app/orchestration")
        if _has_forbidden_import(path, ("research",))
    ]

    assert offenders == []


def test_web_api_does_not_depend_on_cli_tools() -> None:
    offenders = [
        str(path)
        for path in _python_files("web/api")
        if _has_forbidden_import(path, ("tools",))
    ]

    assert offenders == []


def test_adapters_do_not_depend_on_tools_research_or_web() -> None:
    offenders = [
        str(path)
        for path in _python_files("adapters")
        if _has_forbidden_import(path, ("research", "tools", "web"))
    ]

    assert offenders == []


def test_optimize_does_not_depend_on_research_replay_helpers() -> None:
    offenders = [
        str(path)
        for path in _python_files("optimize")
        if _has_forbidden_import(path, ("research",))
    ]

    assert offenders == []


def test_dashboard_projection_does_not_read_config_or_price_files() -> None:
    projection = Path("web/readmodel/dashboard_projection.py")
    source = projection.read_text(encoding="utf-8")

    assert not _has_forbidden_import(projection, ("config", "tools"))
    assert "prices_path" not in source
    assert "plans/prices.json" not in source
    assert "read_text(" not in source


def test_marketdata_dto_lives_outside_adapters_with_compat_reexport() -> None:
    from adapters.marketdata.base import MarketQuote as CompatMarketQuote
    from core.services.marketdata.types import MarketQuote

    assert CompatMarketQuote is MarketQuote


def test_specs_snapshot_writer_lives_in_orchestration_artifacts() -> None:
    assert Path("app/orchestration/spec_artifacts.py").exists()
    assert not Path("core/instruments/spec_snapshot.py").exists()


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


def test_state_engine_exposes_only_event_authority_entrypoints() -> None:
    state = StateEngine()

    assert hasattr(state, "apply_order_event")
    assert hasattr(state, "apply_fill_event")
    assert not hasattr(state, "apply")


def test_runtime_main_chain_does_not_call_legacy_state_apply() -> None:
    runtime_source = Path("app/runtime.py").read_text(encoding="utf-8")

    assert ".state.apply(" not in runtime_source


def test_runtime_uses_scope_not_environment_for_datastore_authority() -> None:
    runtime_source = Path("app/runtime.py").read_text(encoding="utf-8")
    factory_source = Path("app/runtime_factory.py").read_text(encoding="utf-8")
    universe_source = Path("app/universe_runtime.py").read_text(encoding="utf-8")

    assert "self.environment" not in runtime_source
    assert "environment:" not in runtime_source
    assert "environment=" not in factory_source
    assert "executor.environment" not in universe_source


def test_runtime_owns_exit_service() -> None:
    runtime = RuntimeFactory.build_local_runtime()

    assert isinstance(runtime.exit_service, ExitService)


def test_exit_service_owns_exit_rules_and_order_factory() -> None:
    service = ExitService()

    assert isinstance(service.exit_rules, ExitRules)
    assert isinstance(service.exit_order_factory, ExitOrderFactory)
