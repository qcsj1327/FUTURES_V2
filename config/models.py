from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


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
    resolve_from_market_data: bool = False
    close_on_roll: bool = False
    cooldown_ticks: int = 0
    main_contract_schedule: dict[str, list[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class InstrumentsSpec:
    trading_sessions: dict[str, list[TradingSessionSpec]] = field(default_factory=dict)
    roll_policy: RollPolicySpec = field(default_factory=RollPolicySpec)
    spec_source: Literal["static", "tqkq"] = "static"
    specs: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class MarketDataSpec:
    mode: Literal["local_file", "tqkq"] = "local_file"
    prices_path: str | None = None
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrokerSpec:
    mode: Literal["simulated", "tqkq"] = "simulated"
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AdaptersSpec:
    market_data: MarketDataSpec = field(default_factory=MarketDataSpec)
    broker: BrokerSpec = field(default_factory=BrokerSpec)


@dataclass(frozen=True)
class RuntimeSpec:
    runtime_id: str
    ticks_live: int
    ticks_dryrun: int
    default_quantity: float
    mode: Literal["local", "dryrun", "live"] = "local"
    warmup_seconds: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    dynamic_exit_enabled: bool = True
    dynamic_stop_loss_vol_mult: float = 3.0
    dynamic_take_profit_vol_mult: float = 5.0
    dynamic_min_stop_loss_pct: float = 0.006
    dynamic_min_take_profit_pct: float = 0.012
    dynamic_max_stop_loss_pct: float = 0.03
    dynamic_max_take_profit_pct: float = 0.06
    active_top_n: int = 0
    rank_window: int = 20
    rank_metric: str = "signal_strength"
    rank_refresh_every: int = 1
    rank_emit_events: int = 1


@dataclass(frozen=True)
class ExecutionSpec:
    max_pending_ticks: int | None = None
    max_rejects_in_window: int | None = None
    reject_window_ticks: int | None = None
    halt_ticks: int | None = None
    min_order_interval_ticks: int | None = None


@dataclass(frozen=True)
class RiskSpec:
    max_position_qty_by_symbol: dict[str, float] = field(default_factory=dict)
    max_risk_ratio: float | None = None
    max_margin_used: float | None = None
    max_notional_by_symbol: dict[str, float] = field(default_factory=dict)


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
class StrategySwitchSpec:
    enabled_by_symbol: dict[str, list[str]] = field(default_factory=dict)
    approval_required: bool = False
    min_score: float = 1.0
    max_enabled_strategies_per_symbol: int = 1


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
    strategy_switch: StrategySwitchSpec = field(default_factory=StrategySwitchSpec)
    execution: ExecutionSpec = field(default_factory=ExecutionSpec)
    risk: RiskSpec = field(default_factory=RiskSpec)
    instruments: InstrumentsSpec = field(default_factory=InstrumentsSpec)
