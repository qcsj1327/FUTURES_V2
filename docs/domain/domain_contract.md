# Domain 字段冻结契约

本文档是 Domain 字段业务语义、冻结规则、边界规则的权威说明。

`domain/*.py` 是字段名、字段类型、默认值、enum value 的当前实现事实来源。两者必须保持一致；如不一致，除非存在明确 Domain migration，否则必须修正文档或实现以恢复一致。

## 1. Domain 冻结规则

`domain/*` 只允许包含：

- enum
- dataclass
- 类型字段
- 默认值

`domain/*` 禁止包含：

- 业务逻辑
- IO 或文件访问
- adapter、broker、runtime、config、projection、UI、app orchestration 调用
- bootstrap 逻辑
- execution-side、projection-side、UI-side 便利字段

冻结字段不得顺手修改。新增、删除、重命名字段，或改变字段语义，必须通过 domain migration，并同步更新本文档。

上层需求必须通过上层 DTO、event、metadata、readmodel、projection 解决。尤其是 execution handoff 字段不得加入 `RiskDecision`。

`metadata` / `raw` / `details` 只能承载观测、诊断或扩展信息，不得绕过 Domain 契约承载 source-of-truth 字段。

## 2. 全局语义

时间：

- `ts` 和 `bar_ts` 统一为 Unix 秒级时间戳。
- adapter 接收到毫秒或微秒时间戳时，必须先归一化为秒级，再进入 domain 对象。

合约身份：

- `symbol` 是系统内基础品种，例如 `au`。
- `instrument_id` 是行情合约。
- `trade_instrument_id` 是交易合约。
- `_main`、`KQ.m@...`、交易所合约、base symbol 不得在没有显式映射层的情况下混用。

价格：

- `last_price` 是最新行情价。
- `expected_price` 是策略侧预期价或参考价。
- `ExecutionOrder.price` 是委托价。
- `ExecutionResult.fill_price` 是最近一次回报成交价。
- `ExecutionResult.avg_fill_price` 是回报成交均价。
- 这些价格字段不能互相代替。缺行情价时，不能用委托价或成交价伪装。

持仓身份：

- `PositionKey = instrument_id + trade_instrument_id + position_side`。
- `PortfolioState.positions` 是真实持仓唯一事实来源。
- `StateSnapshot` 是导出、展示、回放快照，不是 live source of truth。
- pending、submitted、rejected 订单都不是持仓。

## 3. Enums

### Side

| 字段 | 值 | 语义 |
|---|---|---|
| `BUY` | `buy` | 买入方向。 |
| `SELL` | `sell` | 卖出方向。 |
| `NONE` | `none` | 显式无方向。 |

### Decision

| 字段 | 值 | 语义 |
|---|---|---|
| `OPEN_LONG` | `open_long` | 开多。 |
| `OPEN_SHORT` | `open_short` | 开空。 |
| `CLOSE` | `close` | 平仓。 |
| `HOLD` | `hold` | 观望，不交易。 |

### PositionSide

| 字段 | 值 | 语义 |
|---|---|---|
| `LONG` | `long` | 多头持仓方向。 |
| `SHORT` | `short` | 空头持仓方向。 |
| `FLAT` | `flat` | 空仓方向。 |

### SignalStrength

| 字段 | 值 | 语义 |
|---|---|---|
| `STRONG` | `strong` | 强信号。 |
| `MEDIUM` | `medium` | 中等信号。 |
| `WEAK` | `weak` | 弱信号。 |

### TriggerLifecycle

| 字段 | 值 | 语义 |
|---|---|---|
| `CANDIDATE` | `candidate` | 候选信号。 |
| `CONFIRMED` | `confirmed` | 已确认的触发候选。 |
| `TRIGGERED` | `triggered` | 已触发，可进入风控评估。 |
| `DUPLICATE` | `duplicate` | 重复触发。 |
| `BLOCKED` | `blocked` | 执行前被阻断。 |
| `EXPIRED` | `expired` | 执行前过期。 |

### OrderStatus

| 字段 | 值 | 语义 |
|---|---|---|
| `CREATED` | `created` | 订单对象已创建。 |
| `SUBMITTED` | `submitted` | 订单已提交。 |
| `PARTIALLY_FILLED` | `partially_filled` | 订单部分成交。 |
| `FILLED` | `filled` | 订单完全成交。 |
| `CANCELED` | `canceled` | 订单已撤销。 |
| `REJECTED` | `rejected` | 订单被拒绝。 |

### ExecutionStatus

| 字段 | 值 | 语义 |
|---|---|---|
| `SUBMITTED` | `submitted` | 执行已提交，等待 broker 结果。 |
| `PARTIALLY_FILLED` | `partially_filled` | 执行部分成交。 |
| `FILLED` | `filled` | 执行完全成交。 |
| `REJECTED` | `rejected` | 执行被拒绝。 |

## 4. Market / Feature Domain

### FeatureSnapshot

策略或行情上下文附带的特征快照。

| 字段 | 类型 | 默认值 | 语义 |
|---|---|---:|---|
| `ts` | `int` | required | 特征生成时间戳。 |
| `bar_ts` | `int` | required | K 线时间戳。 |
| `bar_time` | `str` | required | K 线时间字符串。 |
| `timeframe` | `str` | required | K 线周期。 |
| `returns` | `float \| None` | `None` | 区间收益。 |
| `bar_return` | `float \| None` | `None` | 当前 K 线收益。 |
| `range` | `float \| None` | `None` | 通用波动区间。 |
| `price_range` | `float \| None` | `None` | 价格区间。 |
| `atr` | `float \| None` | `None` | ATR。 |
| `volume_ratio` | `float \| None` | `None` | 量能比例。 |
| `breakout_level` | `float \| None` | `None` | 突破位。 |
| `moving_average` | `float \| None` | `None` | 移动均线。 |
| `bias` | `float \| None` | `None` | 偏离率。 |

### MarketContext

标准行情上下文。`last_price` 只表示最新行情价，不表示委托价或成交价。

| 字段 | 类型 | 默认值 | 语义 |
|---|---|---:|---|
| `symbol` | `str` | required | 系统内基础品种。 |
| `instrument_id` | `str` | required | 行情合约。 |
| `trade_instrument_id` | `str` | required | 交易合约。 |
| `ts` | `int` | required | 当前时间戳。 |
| `bar_ts` | `int` | required | K 线时间戳。 |
| `bar_time` | `str` | required | K 线时间字符串。 |
| `timeframe` | `str` | required | 周期。 |
| `trading_date` | `str` | required | 交易日。 |
| `market_phase` | `str` | required | 市场阶段。 |
| `market_mode` | `str` | required | 市场模式。 |
| `is_trading_time` | `bool` | required | 当前时间是否可交易。 |
| `last_price` | `float` | required | 最新行情价。 |
| `open` | `float` | required | 开盘价。 |
| `high` | `float` | required | 最高价。 |
| `low` | `float` | required | 最低价。 |
| `close` | `float` | required | 收盘价。 |
| `volume` | `float` | required | 成交量。 |
| `feature_snapshot` | `FeatureSnapshot \| None` | `None` | 可选特征快照。 |
| `raw` | `dict[str, Any] \| None` | `None` | 可选 adapter 原始扩展。 |

`raw` 可承载 adapter 诊断信息，但交易主链不得依赖只存在于 `raw` 的值。

## 5. Signal / Trigger Domain

### SignalCandidate

策略在路由前输出的完整候选信号。

| 字段 | 类型 | 默认值 | 语义 |
|---|---|---:|---|
| `signal_id` | `str` | required | 信号 ID。 |
| `strategy_name` | `str` | required | 策略名。 |
| `symbol` | `str` | required | 系统内基础品种。 |
| `instrument_id` | `str` | required | 行情合约。 |
| `trade_instrument_id` | `str` | required | 交易合约。 |
| `ts` | `int` | required | 信号时间戳。 |
| `bar_ts` | `int` | required | K 线时间戳。 |
| `bar_time` | `str` | required | K 线时间字符串。 |
| `decision` | `Decision` | required | 交易决策。 |
| `side` | `Side` | required | 买卖方向。 |
| `position_side` | `PositionSide` | required | 持仓方向。 |
| `confidence` | `float` | required | 策略置信度。 |
| `strength` | `SignalStrength` | required | 信号强度。 |
| `reason` | `str` | required | 策略原因。 |
| `expected_price` | `float \| None` | `None` | 策略预期价或参考价。 |
| `stop_loss` | `float \| None` | `None` | 策略止损价。 |
| `take_profit` | `float \| None` | `None` | 策略止盈价。 |
| `holding_period_hint` | `int \| None` | `None` | 可选持有周期提示。 |
| `tags` | `list[str]` | `[]` | 策略标签。 |
| `features_ref` | `str \| None` | `None` | 可选特征引用。 |
| `raw` | `dict[str, Any] \| None` | `None` | 可选策略扩展。 |

### SignalDecision

路由后或直接进入触发层的信号决策。`expected_price` 仍是策略侧参考价，不是最终委托价。

| 字段 | 类型 | 默认值 | 语义 |
|---|---|---:|---|
| `decision` | `Decision` | required | 交易决策。 |
| `side` | `Side` | required | 买卖方向。 |
| `strength` | `SignalStrength` | required | 信号强度。 |
| `confidence` | `float` | required | 置信度。 |
| `reason` | `str` | required | 决策原因。 |
| `signal_id` | `str \| None` | `None` | 可选信号 ID。 |
| `strategy_name` | `str \| None` | `None` | 可选策略名。 |
| `symbol` | `str \| None` | `None` | 可选系统内基础品种。 |
| `instrument_id` | `str \| None` | `None` | 可选行情合约。 |
| `trade_instrument_id` | `str \| None` | `None` | 可选交易合约。 |
| `runtime_id` | `str \| None` | `None` | 可选 runtime ID。 |
| `ts` | `int \| None` | `None` | 可选时间戳。 |
| `bar_ts` | `int \| None` | `None` | 可选 K 线时间戳。 |
| `bar_time` | `str \| None` | `None` | 可选 K 线时间字符串。 |
| `position_side` | `PositionSide \| None` | `None` | 可选持仓方向。 |
| `expected_price` | `float \| None` | `None` | 策略预期价或参考价。 |
| `stop_loss` | `float \| None` | `None` | 止损价。 |
| `take_profit` | `float \| None` | `None` | 止盈价。 |
| `tags` | `list[str]` | `[]` | 标签。 |
| `raw` | `dict[str, Any] \| None` | `None` | 可选策略扩展。 |

### TriggerResult

触发层结果，只表达信号是否触发，不负责填充最终委托价等 execution-only 字段。

| 字段 | 类型 | 默认值 | 语义 |
|---|---|---:|---|
| `decision` | `Decision` | required | 交易决策。 |
| `side` | `Side` | required | 买卖方向。 |
| `lifecycle` | `TriggerLifecycle` | required | 触发生命周期。 |
| `triggered` | `bool` | required | 是否触发。 |
| `runtime_id` | `str` | required | runtime ID。 |
| `bar_ts` | `int \| None` | `None` | 可选 K 线时间戳。 |
| `signal_id` | `str \| None` | `None` | 可选信号 ID。 |
| `strategy_name` | `str \| None` | `None` | 可选策略名。 |
| `symbol` | `str \| None` | `None` | 可选系统内基础品种。 |
| `instrument_id` | `str \| None` | `None` | 可选行情合约。 |
| `trade_instrument_id` | `str \| None` | `None` | 可选交易合约。 |
| `ts` | `int \| None` | `None` | 可选时间戳。 |
| `bar_time` | `str \| None` | `None` | 可选 K 线时间字符串。 |
| `position_side` | `PositionSide \| None` | `None` | 可选持仓方向。 |
| `confidence` | `float \| None` | `None` | 可选置信度。 |
| `strength` | `SignalStrength \| None` | `None` | 可选信号强度。 |
| `reason` | `str \| None` | `None` | 可选原因。 |
| `details` | `dict[str, Any]` | `{}` | 触发细节。 |

## 6. Risk Domain

### RiskContext

传入风控逻辑的可选上下文。

| 字段 | 类型 | 默认值 | 语义 |
|---|---|---:|---|
| `reference_price` | `float \| None` | `None` | 风控参考价。 |
| `volatility` | `float \| None` | `None` | 波动率估计。 |
| `risk_level` | `str \| None` | `None` | 风险等级标签。 |
| `current_position_qty` | `float` | `0.0` | 当前持仓数量。 |
| `current_position_side` | `PositionSide \| None` | `None` | 当前持仓方向。 |
| `max_position_qty` | `float \| None` | `None` | 最大持仓数量限制。 |

### RiskDecision

风控层决策，只表达单笔交易是否允许以及原因。

| 字段 | 类型 | 默认值 | 语义 |
|---|---|---:|---|
| `instrument_id` | `str` | required | 行情合约。 |
| `trade_instrument_id` | `str` | required | 交易合约。 |
| `allowed` | `bool` | required | 是否允许执行。 |
| `decision` | `Decision` | required | 交易决策。 |
| `side` | `Side` | required | 买卖方向。 |
| `position_side` | `PositionSide \| None` | required | 持仓方向。 |
| `lifecycle` | `TriggerLifecycle \| None` | required | 从触发层传入的生命周期。 |
| `quantity` | `float \| None` | `None` | 允许执行时的请求数量。 |
| `stop_loss` | `float \| None` | `None` | 止损价。 |
| `take_profit` | `float \| None` | `None` | 止盈价。 |
| `risk_budget` | `float \| None` | `None` | 风险预算。 |
| `reason` | `str \| None` | `None` | 风控原因。 |
| `details` | `dict[str, Any]` | `{}` | 风控细节。 |

`RiskDecision` 不允许包含 `order_price`、`limit_price`、broker 参数或 execution handoff 字段。真实提交所需委托价必须在 risk 之后由 runtime/execution handoff 层生成，并通过 `ExecutionOrder.price` 进入 broker。

## 7. Execution Domain

### ExecutionOrder

提交给 broker adapter 的订单。`price` 是委托价。

| 字段 | 类型 | 默认值 | 语义 |
|---|---|---:|---|
| `instrument_id` | `str` | required | 行情合约。 |
| `side` | `Side` | required | 买卖方向。 |
| `position_side` | `PositionSide` | required | 持仓方向。 |
| `quantity` | `float` | required | 请求委托数量。 |
| `order_type` | `str` | required | 订单类型。 |
| `trade_instrument_id` | `str \| None` | `None` | 交易合约。 |
| `price` | `float \| None` | `None` | 委托价 / 限价。 |
| `stop_loss` | `float \| None` | `None` | 止损价。 |
| `take_profit` | `float \| None` | `None` | 止盈价。 |
| `client_order_id` | `str \| None` | `None` | 客户端订单 ID。 |

### ExecutionResult

broker 执行结果。

| 字段 | 类型 | 默认值 | 语义 |
|---|---|---:|---|
| `success` | `bool` | required | broker 操作是否成功。 |
| `status` | `ExecutionStatus` | required | 执行状态。 |
| `order_id` | `str \| None` | `None` | broker/order ID。 |
| `ts` | `int \| None` | `None` | 执行时间戳。 |
| `fill_price` | `float \| None` | `None` | 最近一次回报成交价。 |
| `reason` | `str \| None` | `None` | broker / execution 原因。 |
| `filled_quantity` | `float \| None` | `None` | 回报已成交数量。 |
| `remaining_quantity` | `float \| None` | `None` | 回报剩余数量。 |
| `avg_fill_price` | `float \| None` | `None` | 平均成交价。 |

partial fill 语义：

- `SUBMITTED`：成交数量可以为空。
- `PARTIALLY_FILLED`：`filled_quantity > 0` 且 `remaining_quantity > 0`。
- `FILLED`：`filled_quantity > 0` 且 `remaining_quantity = 0`。
- `REJECTED`：成交字段可以为空。
- state 和 capital 更新必须使用 `filled_quantity`，不能把 `ExecutionOrder.quantity` 当实际成交量。
- `avg_fill_price` 存在时，position/cash 更新优先使用它；它不得被当作最新行情价。

## 8. Event Domain

### OrderEvent

订单生命周期事件。`quantity` 是请求委托数量。

| 字段 | 类型 | 默认值 | 语义 |
|---|---|---:|---|
| `strategy_name` | `str` | required | 策略名。 |
| `instrument_id` | `str` | required | 行情合约。 |
| `trade_instrument_id` | `str` | required | 交易合约。 |
| `order_id` | `str` | required | 订单 ID。 |
| `side` | `Side` | required | 买卖方向。 |
| `position_side` | `PositionSide` | required | 持仓方向。 |
| `quantity` | `float` | required | 请求委托数量。 |
| `status` | `OrderStatus` | required | 订单状态。 |
| `ts` | `int` | required | 事件时间戳。 |
| `reason` | `str \| None` | `None` | 可选原因。 |
| `client_order_id` | `str \| None` | `None` | 客户端订单 ID。 |
| `runtime_id` | `str \| None` | `None` | runtime ID。 |
| `metadata` | `dict[str, Any]` | `{}` | 可选事件 metadata。 |

### FillEvent

成交事件。`quantity` 是实际成交数量。

| 字段 | 类型 | 默认值 | 语义 |
|---|---|---:|---|
| `strategy_name` | `str` | required | 策略名。 |
| `instrument_id` | `str` | required | 行情合约。 |
| `trade_instrument_id` | `str` | required | 交易合约。 |
| `order_id` | `str` | required | 订单 ID。 |
| `side` | `Side` | required | 买卖方向。 |
| `position_side` | `PositionSide` | required | 持仓方向。 |
| `quantity` | `float` | required | 实际成交数量。 |
| `fill_price` | `float` | required | 成交价。 |
| `ts` | `int` | required | 成交时间戳。 |
| `fill_id` | `str \| None` | `None` | 成交 ID。 |
| `client_order_id` | `str \| None` | `None` | 客户端订单 ID。 |
| `runtime_id` | `str \| None` | `None` | runtime ID。 |
| `metadata` | `dict[str, Any]` | `{}` | 可选成交 metadata。 |

`metadata` 可以承载观测细节，但交易主链必需语义不能只编码在 metadata 中。

## 9. State Domain

### OrderState

当前订单状态。它不是持仓。

| 字段 | 类型 | 默认值 | 语义 |
|---|---|---:|---|
| `order_id` | `str` | required | 订单 ID。 |
| `instrument_id` | `str` | required | 行情合约。 |
| `trade_instrument_id` | `str` | required | 交易合约。 |
| `side` | `Side` | required | 买卖方向。 |
| `position_side` | `PositionSide` | required | 持仓方向。 |
| `quantity` | `float` | required | 请求委托数量。 |
| `status` | `OrderStatus` | required | 订单状态。 |
| `ts` | `int \| None` | `None` | 最近更新时间戳。 |
| `filled_quantity` | `float` | `0.0` | 当前已成交数量。 |
| `avg_fill_price` | `float \| None` | `None` | 已成交均价。 |
| `client_order_id` | `str \| None` | `None` | 客户端订单 ID。 |
| `runtime_id` | `str \| None` | `None` | runtime ID。 |
| `strategy_name` | `str \| None` | `None` | 策略名。 |
| `reason` | `str \| None` | `None` | 可选原因。 |
| `metadata` | `dict[str, Any]` | `{}` | 可选订单 metadata。 |

### PositionState

单个真实持仓快照。

| 字段 | 类型 | 默认值 | 语义 |
|---|---|---:|---|
| `instrument_id` | `str` | required | 行情合约。 |
| `trade_instrument_id` | `str` | required | 交易合约。 |
| `position_side` | `PositionSide` | `PositionSide.FLAT` | 持仓方向。 |
| `quantity` | `float` | `0.0` | 真实持仓数量。 |
| `avg_price` | `float \| None` | `None` | 持仓均价。 |
| `realized_pnl` | `float` | `0.0` | 已实现盈亏。 |
| `unrealized_pnl` | `float` | `0.0` | 未实现盈亏。 |
| `runtime_id` | `str \| None` | `None` | runtime ID。 |
| `strategy_name` | `str \| None` | `None` | 策略名。 |
| `updated_ts` | `int \| None` | `None` | 最近更新时间戳。 |
| `metadata` | `dict[str, Any]` | `{}` | 可选持仓 metadata。 |

### StrategyState

策略运行状态。

| 字段 | 类型 | 默认值 | 语义 |
|---|---|---:|---|
| `strategy_name` | `str` | required | 策略名。 |
| `runtime_id` | `str \| None` | `None` | runtime ID。 |
| `enabled` | `bool` | `True` | 策略是否启用。 |
| `last_signal_id` | `str \| None` | `None` | 最近信号 ID。 |
| `last_bar_ts` | `int \| None` | `None` | 最近 K 线时间戳。 |
| `metadata` | `dict[str, Any]` | `{}` | 可选策略 metadata。 |

### SystemState

系统运行状态。

| 字段 | 类型 | 默认值 | 语义 |
|---|---|---:|---|
| `runtime_id` | `str` | required | runtime ID。 |
| `is_running` | `bool` | `False` | 是否运行中。 |
| `is_paused` | `bool` | `False` | 是否暂停。 |
| `updated_ts` | `int \| None` | `None` | 最近更新时间戳。 |
| `metadata` | `dict[str, Any]` | `{}` | 可选系统 metadata。 |

### PnLSnapshot

盈亏快照。

| 字段 | 类型 | 默认值 | 语义 |
|---|---|---:|---|
| `realized_pnl` | `float` | `0.0` | 已实现盈亏。 |
| `unrealized_pnl` | `float` | `0.0` | 未实现盈亏。 |
| `commission` | `float` | `0.0` | 手续费。 |

### StateSnapshot

导出/回读状态快照。它不是 live 持仓事实来源。

| 字段 | 类型 | 默认值 | 语义 |
|---|---|---:|---|
| `runtime_id` | `str` | required | runtime ID。 |
| `orders` | `list[OrderState]` | `[]` | 订单状态列表。 |
| `positions` | `list[PositionState]` | `[]` | 导出/回读用持仓状态列表。 |
| `strategies` | `list[StrategyState]` | `[]` | 策略状态列表。 |
| `system` | `SystemState \| None` | `None` | 可选系统状态。 |
| `pnl` | `PnLSnapshot` | `PnLSnapshot()` | 盈亏快照。 |

### PositionKey

真实持仓唯一身份。

| 字段 | 类型 | 默认值 | 语义 |
|---|---|---:|---|
| `instrument_id` | `str` | required | 行情合约。 |
| `trade_instrument_id` | `str` | required | 交易合约。 |
| `position_side` | `PositionSide` | required | 持仓方向。 |

### PortfolioState

真实组合状态，持仓 source of truth。

| 字段 | 类型 | 默认值 | 语义 |
|---|---|---:|---|
| `runtime_id` | `str` | required | runtime ID。 |
| `positions` | `dict[PositionKey, PositionState]` | `{}` | 按 `PositionKey` 索引的真实持仓。 |
| `cash` | `float \| None` | `None` | 现金。 |
| `equity` | `float \| None` | `None` | 权益。 |
| `realized_pnl` | `float` | `0.0` | 已实现盈亏。 |
| `unrealized_pnl` | `float` | `0.0` | 未实现盈亏。 |
| `updated_ts` | `int \| None` | `None` | 最近更新时间戳。 |
| `metadata` | `dict[str, object]` | `{}` | 可选组合 metadata。 |

pending order、submitted order、rejected order、lifecycle event 都不得展示或计算为真实持仓。真实持仓只来自 `PortfolioState.positions`。

## 10. Performance Domain

performance 对象只总结历史结果，不参与下单或状态变更。

### ClosedTrade

| 字段 | 类型 | 默认值 | 语义 |
|---|---|---:|---|
| `trade_id` | `str` | required | 交易 ID。 |
| `strategy_name` | `str` | required | 策略名。 |
| `symbol` | `str` | required | 系统内基础品种。 |
| `instrument_id` | `str` | required | 行情合约。 |
| `trade_instrument_id` | `str` | required | 交易合约。 |
| `side` | `Side` | required | 买卖方向。 |
| `position_side` | `PositionSide` | required | 持仓方向。 |
| `quantity` | `float` | required | 平仓数量。 |
| `entry_price` | `float` | required | 入场价。 |
| `exit_price` | `float` | required | 出场价。 |
| `entry_ts` | `int` | required | 入场时间戳。 |
| `exit_ts` | `int` | required | 出场时间戳。 |
| `realized_pnl` | `float` | required | 已实现盈亏。 |
| `commission` | `float` | `0.0` | 手续费。 |
| `reason` | `str \| None` | `None` | 可选平仓原因。 |
| `metadata` | `dict[str, Any]` | `{}` | 可选 performance metadata。 |

### PerformanceSnapshot

| 字段 | 类型 | 默认值 | 语义 |
|---|---|---:|---|
| `ts` | `int` | required | 快照时间戳。 |
| `trading_day` | `str` | required | 交易日。 |
| `strategy_name` | `str` | required | 策略名。 |
| `symbol` | `str` | required | 系统内基础品种。 |
| `instrument_id` | `str` | required | 行情合约。 |
| `trade_instrument_id` | `str` | required | 交易合约。 |
| `total_trades` | `int` | `0` | 总交易数。 |
| `winning_trades` | `int` | `0` | 盈利交易数。 |
| `losing_trades` | `int` | `0` | 亏损交易数。 |
| `win_rate` | `float` | `0.0` | 胜率。 |
| `gross_profit` | `float` | `0.0` | 总盈利。 |
| `gross_loss` | `float` | `0.0` | 总亏损。 |
| `net_profit` | `float` | `0.0` | 净利润。 |
| `max_drawdown` | `float` | `0.0` | 最大回撤。 |
| `sharpe_ratio` | `float \| None` | `None` | 夏普比率。 |
| `profit_factor` | `float \| None` | `None` | 盈亏因子。 |
| `avg_win` | `float \| None` | `None` | 平均盈利。 |
| `avg_loss` | `float \| None` | `None` | 平均亏损。 |
| `metadata` | `dict[str, Any]` | `{}` | 可选 performance metadata。 |

只有上表列出的字段才是当前冻结的 `ClosedTrade` 字段。额外衍生指标必须留在 domain 之外，除非未来 migration 显式加入。

## 11. Migration History

历史 migration 已折叠进当前主契约。本节只记录当前冻结形态的来源，不是第二套 schema。

### v0.2 State / Portfolio Source of Truth

状态层引入 `PositionKey` 和 `PortfolioState`，用于支持多持仓组合。

当前冻结规则：

- `PortfolioState.positions` 是真实持仓 source of truth。
- `PositionKey` 是持仓唯一身份。
- `StateSnapshot` 只用于导出/回读。
- 不允许引入第二套真实持仓模型。

### v0.4 Execution Partial Fill

`ExecutionResult` 包含 partial fill 字段：

- `ExecutionResult.filled_quantity`
- `ExecutionResult.remaining_quantity`
- `ExecutionResult.avg_fill_price`

当前冻结规则：

- partial fill 和 full fill 必须回报真实成交数量。
- state 和 capital 逻辑必须使用实际成交数量。
- 成交数量不能只编码在 `reason`、`metadata` 或 raw broker payload 中。

未来 domain 变更必须在本节新增 migration 说明，并在同一变更中更新上文字段表。
