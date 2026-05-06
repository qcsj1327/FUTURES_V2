from __future__ import annotations

import ast
from pathlib import Path

DOMAIN_ROOT = Path("domain")
ENVELOPE_ONLY_FIELDS = {
    "runtime_profile",
    "datastore_scope",
    "execution_env",
    "broker_profile",
    "submit_mode",
    "is_live",
    "is_simulated_execution",
    "source",
    "payload_type",
    "event_id",
}


def _domain_files() -> list[Path]:
    return sorted(DOMAIN_ROOT.glob("*.py"))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imported_module(node: ast.Import | ast.ImportFrom) -> str:
    if isinstance(node, ast.ImportFrom):
        return node.module or ""
    return ",".join(alias.name for alias in node.names)


def test_domain_files_only_import_standard_typing_dataclasses_enum_and_domain_enums() -> None:
    allowed_exact = {
        "__future__",
        "dataclasses",
        "enum",
        "typing",
        "domain.enums",
        "domain.feature",
    }
    offenders: list[str] = []

    for path in _domain_files():
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Import | ast.ImportFrom):
                module = _imported_module(node)
                if module not in allowed_exact:
                    offenders.append(f"{path}:{module}")

    assert offenders == []


def test_domain_files_do_not_call_io_runtime_adapter_projection_or_web() -> None:
    forbidden_names = {
        "open",
        "print",
        "eval",
        "exec",
        "getattr",
        "setattr",
        "hasattr",
    }
    forbidden_attrs = {
        "read_text",
        "write_text",
        "open",
        "loads",
        "dumps",
        "load",
        "dump",
        "request",
        "submit_order",
        "apply_order_event",
        "apply_fill_event",
    }
    offenders: list[str] = []

    for path in _domain_files():
        for node in ast.walk(_tree(path)):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name):
                if func.id in forbidden_names:
                    offenders.append(f"{path}:{func.id}")
            elif isinstance(func, ast.Attribute) and func.attr in forbidden_attrs:
                offenders.append(f"{path}:{func.attr}")

    assert offenders == []


def test_domain_dataclasses_do_not_contain_runtime_profile_or_envelope_fields() -> None:
    offenders: list[str] = []

    for path in _domain_files():
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id in ENVELOPE_ONLY_FIELDS:
                    offenders.append(f"{path}:{node.target.id}")

    assert offenders == []


def test_risk_decision_does_not_grow_execution_handoff_fields() -> None:
    source = (DOMAIN_ROOT / "risk.py").read_text(encoding="utf-8")
    forbidden = {
        "order_price",
        "limit_price",
        "order_type",
        "client_order_id",
        "broker_params",
        "broker_profile",
        "execution_handoff",
    }

    assert forbidden.isdisjoint(source.split())


def test_order_and_fill_events_do_not_grow_envelope_fields() -> None:
    source = (DOMAIN_ROOT / "event.py").read_text(encoding="utf-8")

    for field in ENVELOPE_ONLY_FIELDS:
        assert f"{field}:" not in source
