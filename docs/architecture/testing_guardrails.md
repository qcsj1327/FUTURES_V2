# Testing Guardrails 契约

本文件是专项契约，专门定义 contracts 与验证命令。
总架构、三平面、主链与层级边界以 `docs/architecture/structure.md` 为准。
字段、类型、默认值与 Domain 语义以 `docs/domain/domain_contract.md` 为准。

本文档定义架构结构守护和 contracts 验证方向。

## 1. 结构边界

对应契约：[structure.md](structure.md)。

contracts 应锁定：

- `domain/*` 不引入逻辑、IO、跨层依赖。
- `core/*` 不 import adapters/app/web/tools，不写文件。
- `strategies/*` 不访问 broker/runtime/state mutation。
- `app/orchestration/*` 不依赖 research 作为 live 主链必需项。
- `web/*` 和 `tools/dashboard_projection.py` 只读 datastore/artifacts。
- 历史 `sandbox` 不得作为 canonical runtime profile、datastore scope 或 artifact scope 出现。
- legacy mode / sandbox / compat alias 不得作为 canonical profile、scope、datastore path、artifact scope 或主链入口出现。
- 新代码、plan、script、测试 fixture 运行模式不得使用旧名称：`simulated_v2`、`live_file`、`tqkq_sim`、`tqkq_live`、`tqkq_dryrun`、`tqkq_live_submit`。
- `Runtime.run_market_once()` 不得作为 production、daemon、`live`、`dryrun` 或 projection 验收入口；contracts 应优先使用 `UniverseRuntime.run_tick()` 或 `SessionBuilder` 装配入口。

## 2. Runtime Profile 隔离

对应契约：[runtime_profiles.md](runtime_profiles.md)、[local_runtime.md](local_runtime.md)。

contracts 应锁定：

- canonical runtime profiles 只保留 `local` / `dryrun` / `live`。
- local runtime 只读 `local_file`。
- local runtime broker profile 固定 `simulated`。
- local runtime submit mode 固定 `none`。
- local execution events 必须 `is_simulated_execution=true`。
- local order id 必须使用 local/simulated 前缀。
- local fill id 必须使用 local/simulated 前缀。
- local artifact 必须 `scope=local`、`is_live=false`、`is_simulated_execution=true`。
- local datastore path 不得包含 `/live/`。
- live runtime 不得 import simulated marketdata producer。
- live runtime 不得读取 `local_file`。
- live runtime 不得 fallback 到 simulated broker。
- dryrun 不得真实提交。
- dryrun artifact 必须 `scope=dryrun`、`is_live=false`、`is_simulated_execution=false`。
- live artifact 必须 `scope=live`、`is_live=true`、`is_simulated_execution=false`。
- dryrun fill 不得作为 live broker fact、live recovery input 或 live promotion fact。
- local order/fill/position/snapshot/artifact 不得作为 live broker fact、live recovery input、live reconciliation input 或 live promotion fact。
- dryrun order/fill/position/snapshot/artifact 不得作为 live broker fact、live recovery input、live reconciliation input 或 live promotion fact。
- projection/UI 默认不得把 local/dryrun/live 合并成单一持仓、成交、权益或风险口径。
- `runtime.mode` 只允许 `local`、`dryrun`、`live`。
- `DEV_START_MODE` 只允许 `local`、`dryrun`、`live`。
- 新 datastore scope 只允许 `local`、`dryrun`、`live`；禁止新写入 `sandbox`。
- runtime 主链禁止调用 `StateEngine.apply(order, ExecutionResult)`；必须通过 Execution Event Translator 生成 `OrderEvent` / `FillEvent`。

## 3. Event / State

对应契约：[event_state_authority.md](event_state_authority.md)、[domain_contract.md](../domain/domain_contract.md)。

contracts 应锁定：

- DataStore event 必须是 envelope + domain payload 结构。
- profile/scope 不得塞入 domain dataclass。
- BrokerAdapter 不得生成 `OrderEvent` / `FillEvent`。
- `ExecutionResult` 不得直接进入 state mutation，必须先转换为 `OrderEvent` / `FillEvent`。
- Execution Event Translator 是 `OrderEvent` / `FillEvent` 唯一 production authority。
- `StateEngine` 只能消费 `OrderEvent` / `FillEvent` 修改 `OrderState` / `PortfolioState` / `PnLSnapshot`。
- `RiskDecision.quantity` 是最终请求数量 authority。
- Execution Handoff / ExecutionEngine 不得二次改数量。
- `RiskDecision` 不包含 `order_type`。
- `RiskDecision` 不包含 `order_price`、`limit_price`、broker 参数或 execution handoff 字段。
- `OrderEvent.quantity` 不得被当作实际成交数量。
- `FillEvent.quantity` 必须来自 broker/execution 回报中的实际成交数量。
- partial/full fill 的 state/capital/PnL 更新必须使用实际成交数量，不得默认使用 requested quantity。
- `PortfolioState.positions` 只能由 StateEngine 修改。
- event metadata 不承载 source-of-truth 字段。

## 4. Projection / Artifact

对应契约：[readmodel_artifacts.md](readmodel_artifacts.md)。

contracts 应锁定：

- projection 默认不得合并 local/dryrun/live 持仓。
- local position 不得被 live recovery 读取。
- manifest 必须包含 plan path、plan sha256 和 redacted effective plan config summary。
- manifest / promotion artifact / approval artifact 必须保存 redacted plan summary。
- manifest / artifact 不得保存账号、token、broker credential、环境变量原文、私密绝对路径。
- local 模拟行情 producer 写出的 quote 必须 `is_simulated=true`。
- TQKQ snapshot writer 写出的 quote 必须 `is_simulated=false`。
- `local_file` 不包含 order/fill/position 字段。

## 5. 推荐验证

```bash
python -m pytest tests/contracts -k "domain or structure or runtime_mode or local_file or simulated_execution or datastore_scope or dashboard or projection" -q
python -m ruff check docs tests/contracts app config core adapters tools web strategies
git diff --check
```
