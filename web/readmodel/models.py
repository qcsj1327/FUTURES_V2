from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RunListItem:
    runtime_id: str
    created_at: str | None
    approved: bool | None
    router_mode: str | None
    universe_symbols: list[str]
    strategy_names: list[str]
    plan_sha256: str | None
    manifest_path: str


@dataclass(frozen=True)
class RunReadModel:
    runtime_id: str
    created_at: str | None
    candidate_id: str | None
    manifest_path: str

    # plan metadata (from manifest.plan)
    plan_path: str | None
    plan_sha256: str | None
    plan_config: dict[str, Any]

    # artifacts payloads (from manifest.artifacts references)
    current_summary: dict[str, Any]
    candidate_summary: dict[str, Any]
    decision: dict[str, Any]
    approved: dict[str, Any] | None

    thresholds: dict[str, Any]
    warnings: list[str]
    optional_warnings: list[str] = field(default_factory=list)
