# Event / State Authority 契约

本文件是专项契约，专门定义 event / state authority。
总架构、三平面、主链与层级边界以 `docs/architecture/structure.md` 为准。
字段、类型、默认值与 Domain 语义以 `docs/domain/domain_contract.md` 为准。

本文档定义交易事实由谁生产、如何进入 state，以及 order、fill、position、pending 的边界。

## 1. Authority 表

| 事实 / Event | authority / 允许生产者 |
|---|---|
| market quote | marketdata adapter / local_file producer |
| local_file quote | TQKQ snapshot writer / local simulated quote producer / test fixture |
| signal candidate | StrategySet / strategy |
| routed decision | Signal Router |
| trigger lifecycle | TriggerEngine |
| portfolio allocation | PortfolioEngine |
| final request quantity | RiskEngine via `RiskDecision.quantity` |
| risk decision | RiskEngine |
| execution handoff fields | Execution Handoff / Order Builder |
| execution order | ExecutionEngine |
| broker execution result | BrokerAdapter |
| order event | Execution Event Translator |
| fill event | Execution Event Translator |
| order state update | StateEngine |
| position update | StateEngine |
| portfolio state mutation | StateEngine |
| pnl update | StateEngine |
| state snapshot | StateEngine snapshot export / runtime snapshot service |
| promotion proposal / decision / approved artifact | optimize/promoter |
| artifact manifest | artifact writer / optimize/promoter / daemon runner |
| projection | projection/readmodel |
| UI viewmodel | web readmodel / UI layer |

## 2. State Mutation 规则

- `PortfolioState` 只能由 StateEngine 修改。
- `ExecutionResult` 不得直接修改 state，必须先由 Execution Event Translator 转换为 `OrderEvent` / `FillEvent`。
- `StateEngine` 只能消费 `OrderEvent` / `FillEvent` 进入 state transition，不得直接消费 broker adapter 对象。
- `StateEngine.apply(order, result)` 如果在迁移期仍存在，只能作为 legacy test helper；runtime 主链禁止调用，最终必须删除。
- `OrderEvent` 只能表达订单生命周期，不能表达真实持仓。
- `FillEvent` 只能在存在实际成交事实时产生。
- partial/full fill 均必须使用 `ExecutionResult.filled_quantity` 或 broker 回报中的真实成交数量。
- `FillEvent.quantity` 是实际成交数量，不得默认使用 `ExecutionOrder.quantity`。
- `ExecutionResult.avg_fill_price` 存在时，state/capital/PnL 成本更新优先使用它。
- Runtime 不得直接 append position。
- BrokerAdapter 不得直接更新 `PortfolioState`。
- Projection 不得回写交易事件。
- UI 不得生成交易事实。

## 3. DataStore Event Envelope

DataStore event envelope 必须与 domain payload 分离。最小 envelope 字段：

```text
schema_version
event_id
event_type
runtime_id
runtime_profile
datastore_scope
execution_env
broker_profile
submit_mode
is_live
is_simulated_execution
generated_at
source
payload_type
```

规则：

- envelope 承载 profile/scope/source 信息。
- payload 承载 `OrderEvent`、`FillEvent`、lifecycle event、snapshot 或 artifact reference。
- 不得为了存储方便把 envelope 字段新增到 `domain/*` dataclass。
- 不得只在 metadata 中保存 envelope 必需字段。
- local/dryrun/live 的 envelope 字段必须与 datastore path 和 artifact scope 一致。
- metadata 可以承载观测诊断，但不得承载 source-of-truth 字段。
- `local` / `dryrun` event 不得迁移、复制或转换为 `live` event。
- `live` state 只能由 `live` scope 的 `OrderEvent` / `FillEvent` 或显式 live recovery/reconciliation event 驱动。

## 4. 持仓、订单、pending

真实持仓：

- 只来自 `PortfolioState.positions`。
- 以 `PositionKey` 唯一识别。
- 只能由 StateEngine 修改。

订单：

- `OrderState`、order event、lifecycle event 表示订单生命周期。
- `SUBMITTED` / pending 不是持仓。

成交：

- `FillEvent.quantity` 是实际成交数量。
- partial fill 必须使用 `ExecutionResult.filled_quantity` 更新 state/capital/PnL。
- full fill 也必须以 broker 回报的真实成交数量为准，不得默认使用 requested quantity。
- `ExecutionResult.avg_fill_price` 存在时，position/cash/PnL 成本更新优先使用它。

估值：

- position quantity 来自 `PortfolioState.positions`。
- market valuation 来自最新 marketdata quote。
- avg_fill_price 只用于成本基准。
- 禁止使用 fill_price 作为当前持仓市值。

展示：

- 持仓区不能把 pending/order 数量算成持仓。
- 待成交/挂单区可以展示 pending/submitted order。
- 生命周期统计可以展示 raw event 统计，但标题必须明确是生命周期统计，或按 order_id 最新状态聚合。
- local/dryrun/live 持仓必须分 scope 展示。
- local/dryrun 持仓不得作为 live 持仓、live 风险敞口、live 对账或 live recovery 输入。
