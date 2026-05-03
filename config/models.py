from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class UniverseSpec:
    symbols: list[str]


@dataclass(frozen=True)
class StrategySpec:
    name: str
    params: dict[str, Any]
    symbols: list[str]
    priority: int = 100
    weight: float = 1.0


@dataclass(frozen=True)
class RouterSpec:
    mode: str = "priority"         # priority | weighted_vote | netting
    tie_breaker: str = "priority"  # priority | lex


@dataclass(frozen=True)
class TradingSessionSpec:
    start: str
    end: str


@dataclass(frozen=True)
class RollPolicySpec:
    mode: str = "fixed_contract"
    contracts: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class InstrumentsSpec:
    trading_sessions: dict[str, list[TradingSessionSpec]] = field(default_factory=dict)
    roll_policy: RollPolicySpec = field(default_factory=RollPolicySpec)


@dataclass(frozen=True)
class MarketDataSpec:
    mode: str = "simulated"  # simulated | simulated_v2 | live_file | tqkq
    prices_path: str | None = None
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AdaptersSpec:
    market_data: MarketDataSpec = field(default_factory=MarketDataSpec)


@dataclass(frozen=True)
class RuntimeSpec:
    runtime_id: str
    ticks_live: int
    ticks_sandbox: int
    default_quantity: float
    stop_loss: float | None = None
    take_profit: float | None = None


@dataclass(frozen=True)
class DataStoreSpec:
    store_root: Path = Path("data/store")
    artifacts_root: Path = Path("data/artifacts")
    approved_dir: Path = Path("data/artifacts/approved")
    decisions_dir: Path = Path("data/artifacts/decisions")
    summaries_dir: Path = Path("data/artifacts/summaries")
    manifests_dir: Path = Path("data/artifacts/manifests")


@dataclass(frozen=True)
class PromotionSpec:
    min_events: int = 50
    min_success_rate_improvement: float = 0.01
    max_consecutive_failures: int = 3
    write_summary: bool = True
    write_decision: bool = True
    write_manifest: bool = True
    write_approved: bool = True


@dataclass(frozen=True)
class RunPlan:
    schema_version: int
    env: str
    universe: UniverseSpec
    strategies: list[StrategySpec]
    adapters: AdaptersSpec
    runtime: RuntimeSpec
    datastore: DataStoreSpec
    promotion: PromotionSpec
    router: RouterSpec
    instruments: InstrumentsSpec = field(default_factory=InstrumentsSpec)
