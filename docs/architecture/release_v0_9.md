v0.9-multisymbol-multistrategy Release Notes

概览

v0.9 将 futures_v2 从“单品种单策略 + 审计闭环”升级为 多品种、多策略、配置驱动、可审计可复现的期货交易系统。
核心目标是：生产链路 + 学习链路 + 晋升链路三平面贯通，且 live/sandbox 数据不污染，晋升只输出产物，不自动改生产。

Tag：v0.9-multisymbol-multistrategy

⸻

1. 新增核心能力

1.1 多品种 Universe 执行

* 新增 app/universe_runtime.py：单 tick 内对 universe.symbols 获取价格快照并执行多品种决策。
* MarketDataAdapter 增加批量接口 get_last_prices(symbols) -> dict[str, float]：
    * adapters/marketdata/base.py
    * adapters/marketdata/simulated_market_data.py

1.2 多策略 StrategySet + 冲突路由

* 新增 strategies/strategy_set.py：
    * StrategySet.generate(prices) 产出 TaggedDecision(strategy_name, decision)（不依赖 domain 内的 strategy_name 字段）
* 新增可配置路由器 core/signal_router/router.py：
    * priority：按 priority 选一个
    * weighted_vote：按 weight 投票选 Decision（支持 tie_breaker）
    * netting：对 LONG/SHORT 加权净额；CLOSE 优先；平衡则 HOLD

1.3 策略参数真正生效（晋升产物=参数）

* 新增 strategies/parametrized_strategy.py：参数包装器（force_decision / by_symbol）
* strategies/registry.py：
    * 保留旧接口（StrategyRegistry.register/all/get）兼容 orchestrator/runner
    * 新增严格工厂：StrategyRegistry.create(name, params)（无 silent fallback）
    * 增加 alias：simple_strategy_alt（多策略配置测试/演示）

1.4 配置层 RunPlan（配置驱动运行）

* 新增 config/models.py：RunPlan 结构（universe / strategies / runtime / promotion / datastore / router）
* config/loader.py：
    * 完整 JSON 反序列化
    * 严格 key 校验（unknown key 直接报错）
    * router.mode/tie_breaker 合法性校验
* config/defaults.py：默认计划（用于无 config 文件时）

1.5 新编排入口：run_plan（终局主入口）

* scripts/run_plan.py：
    * python -m scripts.run_plan --config plan.json --runtime-id <id> --clean
    * 端到端：live → sandbox → promote → artifacts
    * runtime_id 作为 session 参数贯穿（不再依赖 RuntimeConfig 可写）

1.6 审计闭环增强：manifest 自包含 plan metadata

* optimize/promoter/manifest_artifact.py 增强：
    * manifest 内包含 plan.path / plan.sha256 / plan.config
* tests/contracts/test_manifest_includes_plan_contracts.py 锁死该行为

1.7 Tests 目录重构

将 tests/contracts 中非不变量测试下沉到：

* tests/unit/
* tests/integration/
* tests/regression/
* tests/replay/

tests/contracts/ 收敛为“系统不变量锁死”集合。

1.8 分层合规：research 不再静态依赖 app

* research/replay.py、research/market_replay.py 去掉 from app... 静态 import
* 改为 lazy runtime bindings（importlib），并使用正确的 mypy per-file 指令
* 通过越层扫描：rg "from app|import app" research 输出为 0

⸻

2. 运行方式

2.1 一键运行（推荐）

python -m scripts.run_plan --config plan.json --runtime-id r_multi --clean

2.2 无配置文件（用默认 plan）

python -m scripts.run_plan --runtime-id r_default --clean

⸻

3. 数据与产物（目录结构）

3.1 DataStore（append-only source of truth）

* data/store/live/<runtime_id>/...
* data/store/sandbox/<runtime_id>/...

内容：

* order_events.jsonl
* fill_events.jsonl（每 tick 必写 execution event）
* portfolio_snapshots.jsonl
* snapshots/portfolio_<ts>.pkl（可回读）

3.2 Artifacts（晋升/审计）

* data/artifacts/summaries/
    * current_<rid>.json
    * candidate_<rid>.json
* data/artifacts/decisions/
    * decision_<rid>_<ts>.json
* data/artifacts/approved/
    * approved_cand_<rid>.json（仅 approved=True 时）
* data/artifacts/manifests/
    * manifest_<rid>_<ts>.json（索引以上全部，且包含 plan 元信息）

⸻

4. Promotion Plane（晋升链路）

* optimize/promoter/promote_from_datastore.py：store → replay → summary → gate → decision
* optimize/promoter/promotion_gate.py：阈值门控（min_events / success_rate improvement / max_fail_streak）
* optimize/promoter/approved_config.py：approved 才写 approved_config artifact
* optimize/promoter/summary_artifact.py：写 summaries
* optimize/promoter/decision_artifact.py：写 decision
* optimize/promoter/manifest_artifact.py：写 manifest（含 plan metadata）

原则：

* 允许自动产生候选与决策
* 不允许自动修改 live runtime（只能输出 artifact，下一次 session 才可显式 apply）

⸻

5. Web/中文映射（预留接口点）

v0.9 完成了 Web 层所需的“只读审计数据模型基础”：
Web/ReadModel 应读取 manifests + artifacts，并可做 code→中文映射（未在 v0.9 强制实现）。

建议落点：

* web/viewmodels/zh_mapping.py：reason/router/promotion code → zh label
* Web API 只读 data/artifacts/* 与 data/store/*

⸻

6. 关键 contracts（不变量）

冻结/分层/主链

* tests/contracts/test_domain_contracts.py
* tests/contracts/test_structure_boundaries.py
* tests/contracts/test_chain_contracts_final_lock.py
* tests/contracts/test_main_chain_no_fallback.py

数据隔离与 session_id

* tests/contracts/test_datastore_*_isolation*.py
* tests/contracts/test_run_plan_runtime_id_contracts.py

配置驱动

* tests/contracts/test_run_plan_config_loader_contracts.py
* tests/contracts/test_config_loader_strictness_contracts.py

路由与多品种

* tests/contracts/test_signal_router_modes_contracts.py
* tests/contracts/test_universe_runtime_contracts.py
* tests/contracts/test_universe_runtime_event_count_contracts.py

策略参数

* tests/contracts/test_strategy_params_contracts.py
* tests/contracts/test_strategy_params_by_symbol_contracts.py

审计闭环

* tests/contracts/test_manifest_includes_plan_contracts.py
* tests/contracts/test_replay_manifest_plan_summary_contracts.py

⸻

7. 已知限制（后续方向）

* live 行情与 live broker 尚未实现（目前 simulated）
* StrategyEngine 本身未按 params 内部建模，参数通过 wrapper 生效（终局可升级为每策略 schema/validator）
* research legacy replay 仍通过 lazy bindings 间接使用 app（静态越层为 0，运行时仍复用 app）

