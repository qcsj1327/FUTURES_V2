# futures_v2 架构结构契约

本文档是 `futures_v2` 当前架构的总入口，只定义总架构、三平面、标准主链、层级职责摘要和全局边界。运行模式、local runtime、event/state authority、readmodel/artifact、contracts、生产强化和历史说明由专项文档承接。

字段、类型、默认值、enum value 与 Domain 字段语义以 [Domain 字段冻结契约](../domain/domain_contract.md) 为准。本文档不得重新定义 Domain 字段，也不得把 execution、projection、UI 字段塞回 `domain/*`。

## 1. 文档权威层级

1. [domain_contract.md](../domain/domain_contract.md)：Domain 字段、类型、默认值、enum value、字段语义。
2. [structure.md](structure.md)：总架构、三平面、主链、层级职责、全局边界。
3. [runtime_profiles.md](runtime_profiles.md)：`local` / `dryrun` / `live` canonical runtime profile 专项契约。
4. [local_runtime.md](local_runtime.md)：`local_file`、模拟行情、模拟成交、local scope 隔离专项契约。
5. [event_state_authority.md](event_state_authority.md)：event producer authority、StateEngine authority、PortfolioState source of truth 专项契约。
6. [readmodel_artifacts.md](readmodel_artifacts.md)：projection/readmodel、artifact/manifest、UI 只读边界专项契约。
7. [testing_guardrails.md](testing_guardrails.md)：contracts 测试清单与验证命令专项契约。
8. [production_hardening.md](production_hardening.md)：生产强化路线；记录未全部落地的目标、风险和后续增强。
9. [release_v0_9.md](release_v0_9.md)：历史说明；不作为当前结构契约。

## 2. 三平面

系统只承认三条平面：

1. **交易执行平面 / Command Plane**
   - 负责行情读取、策略生成、路由、触发、组合、风控、执行、状态更新。
   - 这是唯一会影响订单、成交、持仓、PnL 的主链。

2. **观测读模型平面 / Query Plane**
   - 负责从 datastore、artifacts、`local_file` 读取事件、汇总、projection、web readmodel、UI 展示。
   - 只能读、聚合、投影、展示，不能下单，不能改运行状态，不能伪造交易事实。

3. **研究与晋升平面 / Research & Promotion Plane**
   - 负责离线回放、研究分析、策略评分、候选参数、审批产物。
   - 可以输出 proposal、decision、approved、manifest 等 artifact，但不得自动热改 `live` runtime。

## 3. 全局硬约束摘要

- canonical runtime profiles 只有 `local` / `dryrun` / `live`。
- `local` 允许模拟成交，但所有交易事实必须属于 local / simulated scope。
- `local` / `dryrun` / `live` 的 datastore、artifact、event、position、projection 不得混写。
- `RiskDecision` 不承载 `order_price`、`limit_price`、broker 参数或 execution handoff 字段。
- `ExecutionResult` 必须转换为 `OrderEvent` / `FillEvent` 后才能进入 StateEngine。
- StateEngine 是 `PortfolioState`、`OrderState`、`PnLSnapshot` 的唯一 state mutation authority。
- `PortfolioState.positions` 是真实持仓唯一来源。
- pending order、submitted order、rejected order、lifecycle event 都不是真实持仓。
- projection/readmodel 只读，不得修仓，不得生成或伪造交易事实。

完整字段语义见 [domain_contract.md](../domain/domain_contract.md)。完整 profile/scope 隔离规则见 [runtime_profiles.md](runtime_profiles.md)、[local_runtime.md](local_runtime.md)、[event_state_authority.md](event_state_authority.md)、[readmodel_artifacts.md](readmodel_artifacts.md)。

## 4. 标准交易主链

当前标准路径：

```text
RunPlan / Config
→ SessionBuilder
→ MarketData + Broker + Instrument Services
→ UniverseRuntime
→ StrategySet
→ Signal Router
→ Runtime
→ TriggerEngine
→ PortfolioEngine
→ RiskEngine
→ Execution Handoff / Order Builder
→ ExecutionEngine
→ BrokerAdapter
→ ExecutionResult
→ Execution Event Translator
→ OrderEvent / FillEvent
→ StateEngine
→ OrderState / PortfolioState / PnLSnapshot
→ DataStore Events / Artifacts
```

主链 DTO 边界：

```text
MarketContext / FeatureSnapshot
→ SignalCandidate
→ SignalDecision
→ TriggerResult
→ PortfolioAllocation
→ RiskContext + RiskDecision
→ ExecutionHandoff
→ ExecutionOrder
→ ExecutionResult
→ OrderEvent / FillEvent
→ OrderState / PortfolioState / PnLSnapshot
```

`PortfolioAllocation` 与 `ExecutionHandoff` 是主链上层 DTO，不属于 `domain/*` 冻结 dataclass。不得为了落地这些概念修改 Domain 契约。

## 5. 层级职责摘要

- `RunPlan / Config`：描述运行模式、universe、策略、adapter、broker、risk、execution、datastore、router、promotion。
- `SessionBuilder`：按 plan 装配 marketdata、broker、runtime、instrument resolver、datastore、artifact writer。
- `UniverseRuntime`：多品种、多策略 tick 主入口，只负责 orchestration，不拥有交易事实 authority。
- `StrategySet`：对每个 symbol 调策略，产出带策略身份的 signal。
- `Signal Router`：只做多策略信号选择和冲突处理，输出单个 `SignalDecision` 或空决策。
- `Runtime`：只执行已经路由后的单个交易决策。
- `TriggerEngine`：判断信号是否触发，输出 `TriggerResult`。
- `PortfolioEngine`：输出组合分配建议、risk budget、max quantity、allocation reason；不得输出最终下单事实，不得修改真实持仓。
- `RiskEngine`：判断单笔交易是否允许，输出 `RiskDecision`；`RiskDecision.quantity` 是最终请求下单数量 authority。
- `Execution Handoff / Order Builder`：在 risk 之后、execution 之前生成执行侧 DTO，例如委托价、订单类型、client order id；不得修改 `RiskDecision.quantity`。
- `ExecutionEngine`：构造 `ExecutionOrder` 并调用 broker；不得直接修改 state。
- `BrokerAdapter`：外部 broker 边界，只返回 `ExecutionResult`，不得生成 `OrderEvent` / `FillEvent`，不得修改 state。
- `Execution Event Translator`：唯一负责把 `ExecutionResult` 翻译为 `OrderEvent` / `FillEvent`。
- `StateEngine`：唯一允许修改 `OrderState`、`PortfolioState`、`PnLSnapshot` 的组件；只能消费 `OrderEvent` / `FillEvent`。

`UniverseRuntime` 与 `Runtime` 的边界：

- `UniverseRuntime` 是多品种、多策略 orchestration loop。
- `Runtime` 是单个交易决策的 execution coordinator。
- `Runtime` 不拥有 universe lifecycle，不负责 symbol scheduling，不负责 strategy discovery。
- `Runtime.run_market_once()` 不属于 canonical 主链入口；生产、daemon、`live`、`dryrun`、projection 验收路径不得依赖该 helper。

## 6. 专项边界摘要

### Domain

`domain/*` 只允许 enum、dataclass、类型字段和默认值。Domain 字段、字段语义、价格语义、合约身份、`PositionKey`、`PortfolioState.positions` 等冻结规则见 [domain_contract.md](../domain/domain_contract.md)。

### Runtime Profile

当前 canonical runtime profile 只保留 `local` / `dryrun` / `live`。旧 runtime 名称不提供兼容层，只允许出现在历史名称、迁移说明、禁止项或 contract test 中。完整规则见 [runtime_profiles.md](runtime_profiles.md)。

`local` 是统一模拟调试模式，读取 `local_file`，走 simulated execution，所有交易事实只能写入 local scope。完整 local/local_file/simulated execution 规则见 [local_runtime.md](local_runtime.md)。

### Event / State Authority

交易事实必须沿 `ExecutionResult → Execution Event Translator → OrderEvent / FillEvent → StateEngine` 进入 state。StateEngine 是 state mutation authority，`PortfolioState.positions` 是真实持仓唯一来源。完整 producer authority、event envelope、pending/order/fill/position 边界见 [event_state_authority.md](event_state_authority.md)。

### Readmodel / Artifact

projection/readmodel/UI 属于 query plane，只能读取 datastore/artifacts/`local_file` 并投影展示，不得修仓或生成交易事实。artifact、manifest、scope、UI 只读边界见 [readmodel_artifacts.md](readmodel_artifacts.md)。

### Testing

contracts 应锁定结构边界、runtime profile 隔离、event/state authority、projection/artifact 边界。测试清单与推荐验证命令见 [testing_guardrails.md](testing_guardrails.md)。

## 7. 生产强化与历史说明

[production_hardening.md](production_hardening.md) 只记录生产强化路线、未全部落地的目标、风险和后续增强。它不作为当前已落地结构契约；若与本文档或专项契约冲突，以本文档和专项契约为准。

[release_v0_9.md](release_v0_9.md) 是历史发布说明。文中的 runtime mode、sandbox、路径结构和部分命名属于历史语义，不作为当前结构契约或兼容层依据。

## 8. 结论

当前系统是多模式、多品种、多策略、三平面隔离、event/state authority 锁定的交易系统结构。任何后续修改必须先遵守 Domain 契约、结构总契约、runtime profile 隔离、event/state authority、readmodel/artifact 只读边界和 contracts 守护。
