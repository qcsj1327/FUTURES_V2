# futures_v2 生产强化路线

本文档是生产强化 roadmap，记录未全部落地的目标、风险和后续增强方向，不作为当前已落地结构契约。

当前已生效的总架构、三平面、主链和层级边界以 [structure.md](structure.md) 为准。Domain 字段语义以 [domain_contract.md](../domain/domain_contract.md) 为准。runtime profile、local runtime、event/state authority、readmodel/artifact、testing guardrails 以对应专项契约为准。

若本文档与 `structure.md` 或专项契约冲突，以 `docs/README.md` 当前权威文档索引及对应专项契约为准。

## 1. 目标

生产强化的目标是让 `live` runtime profile 具备稳定、可恢复、可审计、可隔离的真实交易能力。

生产强化应建立在当前结构契约之上。以下内容是强化前提和设计方向，不替代当前契约：

- canonical runtime profile 以 `local / dryrun / live` 为准。
- `PortfolioState.positions` 是真实持仓唯一来源。
- local/dryrun/live 的 datastore、artifact、event、position、projection 必须严格隔离。
- projection/readmodel 只能聚合和展示事实，不能生成或修正交易事实。
- strategy/risk 不拥有 live authority。
- broker truth 必须先进入 `ExecutionResult`。
- `ExecutionResult` 必须经 Execution Event Translator 转换为 `OrderEvent` / `FillEvent`。
- `StateEngine` 只能消费 `OrderEvent` / `FillEvent` 修改 `OrderState`、`PortfolioState`、`PnLSnapshot`。
- BrokerAdapter 不得生成 `OrderEvent` / `FillEvent`，不得修改 state。
- Runtime 不得直接改仓。

生产强化的核心目标：

- 内存状态与 broker/柜台状态可持续对账。
- 重启、网络抖动、重复 tick、重复回报不会导致重复下单或重复记仓。
- 多品种 tick 堆积不会拖垮全局主链。
- local、dryrun、live 三类 runtime profile 的交易事实完全隔离。
- dryrun order/fill 只能是 dryrun execution fact，不得作为 live broker fact、live recovery input 或 live promotion fact。
- UI 上的关键交易事实可以追溯到原始 event。
- manifest 足够支持复盘、恢复和合规审计，且只保存 redacted plan summary，不保存账号、token、broker credential 或环境变量原文。
- recovery/replay 不会污染 live state。

## 2. AuditService 对账循环

- 周期性对比 live `PortfolioState` 与 broker/柜台返回的权益、保证金、持仓。
- 发现偏差时写入告警事件，并可按阈值挂起新交易。

AuditService 只对 `live` scope 生效。`dryrun` 可以做一致性检查，但不得命名为 broker reconciliation，不得将 dryrun state 或 dryrun fill 当作 broker truth。

建议策略：

- 默认对账周期：5 分钟。
- 对账对象：权益、可用资金、保证金占用、每个 `PositionKey` 的数量和方向。
- 偏差分级：info、warning、critical。
- critical 级偏差触发交易挂起，只允许人工恢复。

边界：

- AuditService 不直接修正 `PortfolioState`。
- 自动修正必须另开显式 reconciliation 设计。
- 对账结果进入 datastore/artifacts，UI 只展示结果，不推断真实持仓。
- reconciliation correction event 必须通过 StateEngine 进入 state。
- projection/readmodel 不得修仓。
- local/dryrun runtime 不参与 live reconciliation。
- dryrun fill 不得参与 live broker 对账。
- dryrun state 不得作为 live 初始状态或 live reconciliation 输入。

## 3. 执行幂等与恢复

目标：

- 同一交易意图在重启、网络抖动、重复 tick、重复 broker 回报下不会重复下单。
- replay/recovery 不会重复记仓、重复扣减 cash 或重复生成 fill。
- 观测平面可以从 signal 追踪到 order、fill、position 和最终状态。

建议策略：

- 信号侧引入稳定的决策身份，例如 `decision_id` 或等价 execution key。
- execution handoff 生成 `client_order_id` 时包含 runtime、symbol、strategy、decision identity。
- ExecutionEngine 或 runtime pending guard 维护短期幂等缓存。
- 建议 broker 回报带稳定 broker order identity。
- BrokerAdapter 只返回 `ExecutionResult`，不得生成 `OrderEvent` / `FillEvent`。
- 目标是让 Execution Event Translator 幂等，同一 broker order update 不重复生成订单事件。
- 目标是让同一 partial/full fill 回报不重复生成 `FillEvent` 或重复累计 filled quantity。
- 后续应验证 `decision_id` 或等价追踪 ID 可透传到 order/fill/lifecycle/projection/artifact。
- 后续应验证 `FillEvent` 的 `fill_id`、event id 或 broker execution identity 可去重。
- 目标是让 fill apply 支持幂等。
- 目标是让 order state transition 支持幂等。
- 目标是让 snapshot write 支持幂等。
- 目标是让 projection rebuild 支持幂等。
- recovery 方向是基于 broker reconciliation + execution records + state snapshot。

边界：

- 不把幂等字段塞进 `RiskDecision`。
- `ExecutionResult` 不得直接进入 state mutation，必须先转换为 `OrderEvent` / `FillEvent`。
- `StateEngine` 只能消费 `OrderEvent` / `FillEvent` 修改状态。
- 当前 `SignalDecision`、`OrderEvent`、`FillEvent` 没有冻结的 `decision_id` 字段；如果需要把它变成 Domain 字段，必须先走 Domain migration。
- 当前可优先用 execution-side DTO、event metadata、datastore 索引实现。
- 不允许从 projection 推断真实 position。
- 不允许从 pending order 推断 exposure。
- 不允许从 local/dryrun snapshot 恢复 live state。
- 不允许从 dryrun fill 恢复 live position。
- 不允许把 local/dryrun event envelope 迁移成 live envelope。

## 4. 多品种行情吞吐

目标：

- 多品种高频 tick 输入时，单个品种阻塞不拖垮所有品种。

建议策略：

- 将行情接收与策略计算拆成生产者-消费者模型。
- 每个 symbol 保留最新快照，策略侧按 tick 或调度周期消费一致快照。
- 对落后队列设置最大长度和丢弃策略，禁止无限积压。
- 同一 symbol 必须保证顺序消费。
- 同一 `PositionKey` 的 state mutation 必须串行。
- 为 `live` profile 增加 tick 延迟、队列深度、symbol lag、broker roundtrip latency 观测指标。

边界：

- 异步化不能改变主链语义。
- 任何并发设计必须保证同一 `PositionKey` 的状态更新顺序。
- 不允许因为异步化绕过 pending guard、risk guard 或 trading session gate。
- 不允许异步 worker 绕过 StateEngine。
- 不允许异步 projection 回写交易状态。

## 5. 策略归因与虚拟分仓

目标：

- 多策略下能清楚区分策略归因。
- UI 支持单策略视图和组合视图。
- 同一品种、同一方向下运行多套策略时，可以展示虚拟分仓。

建议策略：

- `strategy_name` / `strategy_id` 贯穿 signal、order、fill、lifecycle、projection、artifact。
- projection/readmodel 支持按 strategy 聚合。
- UI 支持全品种聚合视图和单策略归因视图。
- virtual position 必须显式标记为 attribution view。
- 组合层保留全局风险约束。
- 策略层只负责 attribution。
- future migration 如需真实分仓身份，可评估升级 `PositionKey`。

边界：

- 当前真实持仓 source of truth 仍是 `PortfolioState.positions`。
- 当前冻结的 `PositionKey` 是 `(instrument_id, trade_instrument_id, position_side)`。
- 当前策略分仓只是 projection/readmodel attribution。
- projection attribution 不得伪装成第二套真实持仓模型。
- UI 必须明确区分真实持仓与 attribution view。
- 如需把 `strategy_id` 变成真实持仓身份的一部分，必须先走 Domain migration。

## 6. Event / Projection 可追溯性

目标：

- UI 上每一笔订单、成交、持仓变化都能追溯到 datastore 原始事件。
- projection/viewmodel 的聚合结果可以反向定位 source event。
- local/dryrun/live 的 event lineage 清晰隔离。

建议策略：

- DataStore event 必须采用 envelope + domain payload 结构。
- lifecycle/order/fill/snapshot 事件保留稳定 event id 或可复现 event key。
- projection 保留 `source_event_ids` 或等价索引。
- projection 保留 event envelope 中的 `runtime_profile`、`datastore_scope`、`event_id`、`source`。
- UI 点击持仓变化时展示相关 order/fill/lifecycle 时间线。
- 目标是让 projection rebuild 可重复生成。

边界：

- projection 可以聚合，但不能删除 raw event 事实。
- projection/readmodel 不得生成交易事实。
- UI 展示的“持仓变化”必须来自真实 fill/state。
- pending/submitted/rejected order 不得展示为真实持仓。
- local/dryrun/live event 不得跨 scope 聚合为单一真实交易流。
- projection 不得把 dryrun fill 展示为 live broker fact。
- projection 不得修改 event envelope 或把 local/dryrun envelope 转成 live envelope。

## 7. Manifest / Artifact 审计增强

目标：

- 每次运行 artifact 可支持复盘、恢复、对账、合规审计。
- manifest 可以明确区分 local/dryrun/live runtime profile。
- artifact schema 升级时必须 versioned、可追踪、可显式 migration，不提供隐式兼容语义。

建议字段：

- runtime_id
- runtime_profile
- datastore_scope
- is_live
- is_simulated_execution
- plan path
- plan sha256
- redacted effective plan summary
- redaction status
- start time / end time
- status: booting / running / final / error
- git commit hash
- dirty worktree 标记
- datastore root
- artifacts root
- schema_version
- generated_at

边界：

- boot artifact 只能标记 `status=booting`。
- 没有真实运行结果时，不得伪装成 `running` 或 `final`。
- manifest 缺失可以降级；manifest schema 损坏必须显式报错。
- local/dryrun/live artifact 不得混写。
- projection artifact 不得伪装成 raw trading artifact。
- manifest / artifact 不得写入账号、密码、token、密钥、broker credential、环境变量原文或私密绝对路径。
- manifest 中的 plan 信息只能保存 path、sha256、redacted effective plan summary。
- local/dryrun artifact 不得作为 live recovery 或 live promotion 输入。

## 8. 后续 Contracts 强化方向

当前已落地的 contracts 清单以 [testing_guardrails.md](testing_guardrails.md) 为准。本文仅记录未来生产强化可能需要新增或强化的测试方向：

- live broker reconciliation contract
- execution idempotency contract
- translator idempotency contract
- recovery replay idempotency contract
- async market throughput contract
- virtual attribution readmodel contract
- audit manifest completeness contract

## 9. 落地顺序建议

1. 继续补 contracts，锁住 current structure contract。
2. 先完成 local/dryrun/live runtime profile 隔离测试。
3. 完成 `ExecutionResult → Execution Event Translator → OrderEvent / FillEvent → StateEngine` authority 与 projection boundary 收口。
4. 补 execution idempotency 与 recovery contracts。
5. 再做 live-only AuditService、redacted manifest schema 与 reconciliation 增强。
6. 最后评估异步行情、virtual attribution、broker reconciliation 是否需要 Domain migration。
