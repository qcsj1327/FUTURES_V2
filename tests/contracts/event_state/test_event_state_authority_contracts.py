from __future__ import annotations

import ast
from pathlib import Path

from core.state.state_engine import StateEngine


def _python_files(root: str) -> list[Path]:
    return sorted(Path(root).rglob("*.py"))


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_broker_adapters_do_not_import_or_produce_order_or_fill_events() -> None:
    offenders: list[str] = []

    for path in _python_files("adapters/broker"):
        imports = _imports(path)
        source = path.read_text(encoding="utf-8")
        if "domain.event" in imports:
            offenders.append(f"{path}:imports domain.event")
        for token in ("OrderEvent(", "FillEvent("):
            if token in source:
                offenders.append(f"{path}:{token}")

    assert offenders == []


def test_execution_event_translator_is_only_core_production_authority_for_events() -> None:
    allowed = {
        Path("core/execution/event_translator.py"),
    }
    offenders: list[str] = []

    for root in ("app", "core", "adapters"):
        for path in _python_files(root):
            if path in allowed:
                continue
            source = path.read_text(encoding="utf-8")
            for token in ("OrderEvent(", "FillEvent("):
                if token in source:
                    offenders.append(f"{path}:{token}")

    assert offenders == []


def test_state_engine_public_api_has_no_execution_result_entrypoint() -> None:
    state = StateEngine()

    assert hasattr(state, "apply_order_event")
    assert hasattr(state, "apply_fill_event")
    assert not hasattr(state, "apply")
    assert not hasattr(state, "apply_execution_result")
    assert not hasattr(state, "record_broker_result")


def test_runtime_main_chain_uses_translator_before_state_engine() -> None:
    source = Path("app/runtime.py").read_text(encoding="utf-8")

    assert "translate_execution_result(" in source
    assert "apply_order_event(translated.order_event)" in source
    assert "apply_fill_event(translated.fill_event)" in source
    assert "apply_execution_result(" not in source
    assert ".state.apply(" not in source


def test_state_engine_does_not_adapt_fill_events_through_execution_dtos() -> None:
    state_path = Path("core/state/state_engine.py")
    state_source = state_path.read_text(encoding="utf-8")
    imports = _imports(state_path)

    assert "domain.execution" not in imports
    assert "ExecutionOrder(" not in state_source
    assert "ExecutionResult(" not in state_source
    assert "def apply_execution_result" not in state_source


def test_state_internal_models_do_not_import_execution_dtos() -> None:
    for path in (
        Path("core/state/position_lifecycle.py"),
        Path("core/state/capital_model.py"),
    ):
        assert "domain.execution" not in _imports(path)


def test_fill_application_is_state_internal_only() -> None:
    assert Path("core/state/application.py").exists()
    assert "class FillApplication" in Path("core/state/application.py").read_text(
        encoding="utf-8"
    )

    offenders: list[str] = []
    for path in _python_files("domain"):
        if "FillApplication" in path.read_text(encoding="utf-8"):
            offenders.append(str(path))

    assert offenders == []
