# Domain Contract Freeze

本文件冻结 futures_v2 上线前 Domain 字段与语义。

从本文件提交后：

- 不再新增 domain 字段
- 不再删除 domain 字段
- 不再修改字段语义
- 不再修改 enum value
- 新需求只能通过上层逻辑、metadata、details、raw 扩展
- 如必须改字段，必须新开 domain migration，不允许顺手改

---

## domain/enums.py

### Side

| 字段 | 值 | 语义 |
|---|---|---|
| BUY | buy | 买入 / 做多方向 |
| SELL | sell | 卖出 / 做空方向 |
| NONE | none | 无方向 |

### Decision

| 字段 | 值 | 语义 |
|---|---|---|
| OPEN_LONG | open_long | 开多 |
| OPEN_SHORT | open_short | 开空 |
| CLOSE | close | 平仓 |
| HOLD | hold | 观望，不交易 |

### PositionSide

| 字段 | 值 | 语义 |
|---|---|---|
| LONG | long | 多头持仓 |
| SHORT | short | 空头持仓 |
| FLAT | flat | 空仓 |

### SignalStrength

| 字段 | 值 | 语义 |
|---|---|---|
| STRONG | strong | 强信号 |
| MEDIUM | medium | 中等信号 |
| WEAK | weak | 弱信号 |

### TriggerLifecycle

| 字段 | 值 | 语义 |
|---|---|---|
| CANDIDATE | candidate | 候选 |
| CONFIRMED | confirmed | 已确认 |
| TRIGGERED | triggered | 已触发 |
| DUPLICATE | duplicate | 重复信号 |
| BLOCKED | blocked | 被阻断 |
| EXPIRED | expired | 已过期 |

### OrderStatus

| 字段 | 值 | 语义 |
|---|---|---|
| CREATED | created | 已创建 |
| SUBMITTED | submitted | 已提交 |
| PARTIALLY_FILLED | partially_filled | 部分成交 |
| FILLED | filled | 完全成交 |
| CANCELED | canceled | 已撤单 |
| REJECTED | rejected | 被拒绝 |

### ExecutionStatus

| 字段 | 值 | 语义 |
|---|---|---|
| SUBMITTED | submitted | 执行已提交 |
| PARTIALLY_FILLED | partially_filled | 部分成交 |
| FILLED | filled | 完全成交 |
| REJECTED | rejected | 执行被拒绝 |

---

## domain/feature.py

### FeatureSnapshot

冻结字段：

| 字段 | 类型 | 语义 |
|---|---|---|
| ts | int | 特征生成时间戳 |
| bar_ts | int | K线时间戳 |
| bar_time | str | K线时间字符串 |
| timeframe | str | 周期 |
| returns | float \| None | 区间收益 |
| bar_return | float \| None | 当前K线收益 |
| range | float \| None | 波动区间 |
| price_range | float \| None | 价格区间 |
| atr | float \| None | ATR |
| volume_ratio | float \| None | 量能比例 |
| breakout_level | float \| None | 突破位 |
| moving_average | float \| None | 均线 |
| bias | float \| None | 偏离率 |

---

## domain/market.py

### MarketContext

冻结字段：

| 字段 | 类型 | 语义 |
|---|---|---|
| symbol | str | 系统内标的 |
| instrument_id | str | 行情合约 |
| trade_instrument_id | str | 交易合约 |
| ts | int | 当前时间戳 |
| bar_ts | int | K线时间戳 |
| bar_time | str | K线时间 |
| timeframe | str | 周期 |
| trading_date | str | 交易日 |
| market_phase | str | 市场阶段 |
| market_mode | str | 市场模式 |
| is_trading_time | bool | 是否交易时间 |
| last_price | float | 最新价 |
| open | float | 开 |
| high | float | 高 |
| low | float | 低 |
| close | float | 收 |
| volume | float | 成交量 |
| feature_snapshot | FeatureSnapshot \| None | 特征快照 |
| raw | dict[str, Any] \| None | 原始行情扩展 |

---

## domain/signal.py

### SignalCandidate

冻结字段：

| 字段 | 类型 | 语义 |
|---|---|---|
| signal_id | str | 信号ID |
| strategy_name | str | 策略名 |
| symbol | str | 系统内标的 |
| instrument_id | str | 行情合约 |
| trade_instrument_id | str | 交易合约 |
| ts | int | 信号时间戳 |
| bar_ts | int | K线时间戳 |
| bar_time | str | K线时间 |
| decision | Decision | 交易决策 |
| side | Side | 买卖方向 |
| position_side | PositionSide | 持仓方向 |
| confidence | float | 置信度 |
| strength | SignalStrength | 信号强度 |
| reason | str | 信号原因 |
| expected_price | float \| None | 预期价格 |
| stop_loss | float \| None | 止损 |
| take_profit | float \| None | 止盈 |
| holding_period_hint | int \| None | 建议持有周期 |
| tags | list[str] | 标签 |
| features_ref | str \| None | 特征引用 |
| raw | dict[str, Any] \| None | 原始扩展 |

### SignalDecision

冻结字段：

| 字段 | 类型 | 语义 |
|---|---|---|
| decision | Decision | 交易决策 |
| side | Side | 买卖方向 |
| strength | SignalStrength | 信号强度 |
| confidence | float | 置信度 |
| reason | str | 原因 |
| signal_id | str \| None | 信号ID |
| strategy_name | str \| None | 策略名 |
| symbol | str \| None | 系统内标的 |
| instrument_id | str \| None | 行情合约 |
| trade_instrument_id | str \| None | 交易合约 |
| runtime_id | str \| None | Runtime ID |
| ts | int \| None | 时间戳 |
| bar_ts | int \| None | K线时间戳 |
| bar_time | str \| None | K线时间 |
| position_side | PositionSide \| None | 持仓方向 |
| expected_price | float \| None | 预期价格 |
| stop_loss | float \| None | 止损 |
| take_profit | float \| None | 止盈 |
| tags | list[str] | 标签 |
| raw | dict[str, Any] \| None | 原始扩展 |

---

## domain/trigger.py

### TriggerResult

冻结字段：

| 字段 | 类型 | 语义 |
|---|---|---|
| decision | Decision | 交易决策 |
| side | Side | 买卖方向 |
| lifecycle | TriggerLifecycle | 触发生命周期 |
| triggered | bool | 是否触发 |
| runtime_id | str | Runtime ID |
| bar_ts | int \| None | K线时间戳 |
| signal_id | str \| None | 信号ID |
| strategy_name | str \| None | 策略名 |
| symbol | str \| None | 系统内标的 |
| instrument_id | str \| None | 行情合约 |
| trade_instrument_id | str \| None | 交易合约 |
| ts | int \| None | 时间戳 |
| bar_time | str \| None | K线时间 |
| position_side | PositionSide \| None | 持仓方向 |
| confidence | float \| None | 置信度 |
| strength | SignalStrength \| None | 信号强度 |
| reason | str \| None | 原因 |
| details | dict[str, Any] | 扩展细节 |

---

## domain/risk.py

### RiskContext

冻结字段：

| 字段 | 类型 | 语义 |
|---|---|---|
| reference_price | float \| None | 参考价格 |
| volatility | float \| None | 波动率 |
| risk_level | str \| None | 风险等级 |
| current_position_qty | float | 当前持仓数量 |
| current_position_side | PositionSide \| None | 当前持仓方向 |
| max_position_qty | float \| None | 最大持仓数量 |

### RiskDecision

冻结字段：

| 字段 | 类型 | 语义 |
|---|---|---|
| instrument_id | str | 行情合约 |
| trade_instrument_id | str | 交易合约 |
| allowed | bool | 是否允许交易 |
| decision | Decision | 交易决策 |
| side | Side | 买卖方向 |
| position_side | PositionSide \| None | 持仓方向 |
| lifecycle | TriggerLifecycle \| None | 触发生命周期 |
| quantity | float \| None | 下单数量 |
| stop_loss | float \| None | 止损 |
| take_profit | float \| None | 止盈 |
| risk_budget | float \| None | 风险预算 |
| reason | str \| None | 原因 |
| details | dict[str, Any] | 扩展细节 |

---

## domain/execution.py

### ExecutionOrder

冻结字段：

| 字段 | 类型 | 语义 |
|---|---|---|
| instrument_id | str | 行情合约 |
| side | Side | 买卖方向 |
| position_side | PositionSide | 持仓方向 |
| quantity | float | 数量 |
| order_type | str | 订单类型 |
| trade_instrument_id | str \| None | 交易合约 |
| price | float \| None | 委托价格 |
| stop_loss | float \| None | 止损 |
| take_profit | float \| None | 止盈 |
| client_order_id | str \| None | 客户端订单ID |

### ExecutionResult

冻结字段：

| 字段 | 类型 | 语义 |
|---|---|---|
| success | bool | 是否成功 |
| status | ExecutionStatus | 执行状态 |
| order_id | str \| None | 订单ID |
| ts | int \| None | 时间戳 |
| fill_price | float \| None | 成交价 |
| reason | str \| None | 原因 |
| filled_quantity | float \| None | 本次成交数量 |
| remaining_quantity | float \| None | 剩余未成交数量 |
| avg_fill_price | float \| None | 平均成交价格 |

---

## domain/event.py

### OrderEvent

冻结字段：

| 字段 | 类型 | 语义 |
|---|---|---|
| strategy_name | str | 策略名 |
| instrument_id | str | 行情合约 |
| trade_instrument_id | str | 交易合约 |
| order_id | str | 订单ID |
| side | Side | 买卖方向 |
| position_side | PositionSide | 持仓方向 |
| quantity | float | 数量 |
| status | OrderStatus | 订单状态 |
| ts | int | 时间戳 |
| reason | str \| None | 原因 |
| client_order_id | str \| None | 客户端订单ID |
| runtime_id | str \| None | Runtime ID |
| metadata | dict[str, Any] | 扩展信息 |

### FillEvent

冻结字段：

| 字段 | 类型 | 语义 |
|---|---|---|
| strategy_name | str | 策略名 |
| instrument_id | str | 行情合约 |
| trade_instrument_id | str | 交易合约 |
| order_id | str | 订单ID |
| side | Side | 买卖方向 |
| position_side | PositionSide | 持仓方向 |
| quantity | float | 成交数量 |
| fill_price | float | 成交价 |
| ts | int | 时间戳 |
| fill_id | str \| None | 成交ID |
| client_order_id | str \| None | 客户端订单ID |
| runtime_id | str \| None | Runtime ID |
| metadata | dict[str, Any] | 扩展信息 |

---

## domain/state.py

### OrderState

冻结字段：

| 字段 | 类型 | 语义 |
|---|---|---|
| order_id | str | 订单ID |
| instrument_id | str | 行情合约 |
| trade_instrument_id | str | 交易合约 |
| side | Side | 买卖方向 |
| position_side | PositionSide | 持仓方向 |
| quantity | float | 数量 |
| status | OrderStatus | 订单状态 |
| ts | int \| None | 时间戳 |
| filled_quantity | float | 已成交数量 |
| avg_fill_price | float \| None | 平均成交价 |
| client_order_id | str \| None | 客户端订单ID |
| runtime_id | str \| None | Runtime ID |
| strategy_name | str \| None | 策略名 |
| reason | str \| None | 原因 |
| metadata | dict[str, Any] | 扩展信息 |

### PositionState

冻结字段：

| 字段 | 类型 | 语义 |
|---|---|---|
| instrument_id | str | 行情合约 |
| trade_instrument_id | str | 交易合约 |
| position_side | PositionSide | 持仓方向 |
| quantity | float | 持仓数量 |
| avg_price | float \| None | 持仓均价 |
| realized_pnl | float | 已实现盈亏 |
| unrealized_pnl | float | 未实现盈亏 |
| runtime_id | str \| None | Runtime ID |
| strategy_name | str \| None | 策略名 |
| updated_ts | int \| None | 更新时间 |
| metadata | dict[str, Any] | 扩展信息 |

### StrategyState

冻结字段：

| 字段 | 类型 | 语义 |
|---|---|---|
| strategy_name | str | 策略名 |
| runtime_id | str \| None | Runtime ID |
| enabled | bool | 是否启用 |
| last_signal_id | str \| None | 最近信号ID |
| last_bar_ts | int \| None | 最近K线时间戳 |
| metadata | dict[str, Any] | 扩展信息 |

### SystemState

冻结字段：

| 字段 | 类型 | 语义 |
|---|---|---|
| runtime_id | str | Runtime ID |
| is_running | bool | 是否运行中 |
| is_paused | bool | 是否暂停 |
| updated_ts | int \| None | 更新时间 |
| metadata | dict[str, Any] | 扩展信息 |

### PnLSnapshot

冻结字段：

| 字段 | 类型 | 语义 |
|---|---|---|
| realized_pnl | float | 已实现盈亏 |
| unrealized_pnl | float | 未实现盈亏 |
| commission | float | 手续费 |

### StateSnapshot

冻结字段：

| 字段 | 类型 | 语义 |
|---|---|---|
| runtime_id | str | Runtime ID |
| orders | list[OrderState] | 订单状态列表 |
| positions | list[PositionState] | 持仓状态列表 |
| strategies | list[StrategyState] | 策略状态列表 |
| system | SystemState \| None | 系统状态 |
| pnl | PnLSnapshot | 盈亏快照 |

---

## domain/performance.py

### ClosedTrade

冻结字段：

| 字段 | 类型 | 语义 |
|---|---|---|
| trade_id | str | 交易ID |
| strategy_name | str | 策略名 |
| symbol | str | 系统内标的 |
| instrument_id | str | 行情合约 |
| trade_instrument_id | str | 交易合约 |
| position_side | PositionSide | 持仓方向 |
| entry_price | float | 开仓价 |
| exit_price | float | 平仓价 |
| quantity | float | 数量 |
| entry_ts | int | 开仓时间 |
| exit_ts | int | 平仓时间 |
| pnl | float | 盈亏 |
| pnl_ratio | float | 盈亏比例 |
| holding_seconds | int | 持有秒数 |
| metadata | dict[str, Any] | 扩展信息 |

### PerformanceSnapshot

冻结字段：

| 字段 | 类型 | 语义 |
|---|---|---|
| ts | int | 时间戳 |
| trading_day | str | 交易日 |
| strategy_name | str | 策略名 |
| symbol | str | 系统内标的 |
| instrument_id | str | 行情合约 |
| trade_instrument_id | str | 交易合约 |
| total_trades | int | 总交易数 |
| winning_trades | int | 盈利交易数 |
| losing_trades | int | 亏损交易数 |
| win_rate | float | 胜率 |
| gross_profit | float | 总盈利 |
| gross_loss | float | 总亏损 |
| net_profit | float | 净利润 |
| max_drawdown | float | 最大回撤 |
| sharpe_ratio | float \| None | 夏普比率 |
| profit_factor | float \| None | 盈亏因子 |
| avg_win | float \| None | 平均盈利 |
| avg_loss | float \| None | 平均亏损 |
| metadata | dict[str, Any] | 扩展信息 |

---

## 全局语义约定

### 时间戳

所有 `ts` / `bar_ts` 字段统一使用 Unix 秒级整数。

adapters 层如果接收到毫秒或微秒时间戳，必须转换为秒级后再进入 domain。

禁止系统内混用秒、毫秒、微秒。

### Side.NONE

`Side.NONE` 是唯一无方向值。

不再新增：

- STAY_NEUTRAL
- NOT_SET
- UNKNOWN

所有逻辑层必须显式处理 `Side.NONE`。

### OrderState.avg_fill_price

`avg_fill_price: float | None` 保持不变。

- None：尚未成交
- float：已有成交均价

逻辑层使用前必须判断：

```python
avg_fill_price is not None
```

### PositionState.quantity

`PositionState.quantity` 表示净持仓数量。

不表示：

- 可用持仓
- 冻结持仓
- 挂单占用

如需表达冻结数量，统一放入：

```python
metadata["frozen_quantity"]
```

### instrument_id / trade_instrument_id

`instrument_id` 表示行情合约。

`trade_instrument_id` 表示交易合约。

所有跨期、换月、主力映射逻辑只能在 adapters / config / portfolio 层处理，不允许改变 domain 语义。

---

## 扩展规则

允许扩展位置：

- raw
- metadata
- details
- tags
- config 层
- strategy 参数
- optimize 参数仓库

禁止扩展位置：

- 不允许直接新增 domain 字段
- 不允许新增 enum value
- 不允许修改字段类型
- 不允许改变字段语义

---

## 代码冻结策略

当前通过 contracts 测试锁定：

- enum value
- dataclass 字段集合
- 字段顺序
- 字段默认值
- frozen / 非 frozen 语义

暂不引入：

- slots=True
- typing.final

如未来需要引入，必须单独开 domain migration。

---

## Domain Migration 规则

如确实必须修改 domain：

1. 新建 migration 文档
2. 明确旧字段 / 新字段 / 迁移原因
3. 更新 contracts
4. 更新所有调用层
5. 单独提交
6. 禁止混入业务开发

默认原则：

domain 不改。

---

## 代码实现约束

### Immutability

除 State 相关结构外，Domain dataclass 默认应使用 frozen=True。

目的：

- 防止 Strategy 修改 MarketContext
- 防止 SignalRouter 修改 SignalDecision
- 防止 Risk / Execution 链路产生隐式副作用

State 相关结构允许非 frozen，因为状态层需要被 StateEngine 更新。

---

### 字段漂移防护

contracts 测试必须锁定：

- __annotations__
- dataclass fields
- 字段顺序
- 默认值
- frozen / 非 frozen 属性

任何字段变更必须导致测试失败。

---

### float 精度约定

Domain 字段继续使用 float，保证序列化与跨层兼容。

涉及累计计算时：

- PnL
- position avg price
- commission
- risk budget

内部计算层可使用 Decimal，最终写回 Domain 时再转换为 float。

禁止在 Domain 字段中直接改为 Decimal。

---

### list / dict 默认值

所有 list / dict 字段必须使用：

field(default_factory=list)
field(default_factory=dict)

禁止使用可变对象作为默认值。

---

### 时间字符串

所有 bar_time 等字符串时间字段统一使用 UTC 表达。

如果 adapters 接收到本地时间，必须在 adapters 层转换为 UTC。

---

### ID 唯一性

以下 ID 必须由上层生成并保证唯一：

- signal_id
- client_order_id
- order_id
- fill_id
- trade_id

Domain 只承载 ID，不负责生成 ID。

---

### 空值语义

所有 None 都必须有明确含义。

逻辑层禁止用 truthy 判断代替显式判断。

推荐：

avg_fill_price is not None

禁止：

avg_fill_price

---

## 冻结结论

domain 是上线前冻结契约。

从本文件提交后，整个开发过程默认不再新增 domain 字段。

所有新增需求必须优先通过：

- 上层逻辑
- metadata
- raw
- details
- config
- strategy 参数
- optimize 参数仓库

实现。

如确实必须修改 domain，必须走 Domain Migration。
### PositionKey

v0.2 State Domain Migration 新增。

冻结字段：

| 字段 | 类型 | 语义 |
|---|---|---|
| instrument_id | str | 行情合约 |
| trade_instrument_id | str | 交易合约 |
| position_side | PositionSide | 持仓方向 |

---

### PortfolioState

v0.2 State Domain Migration 新增。

冻结字段：

| 字段 | 类型 | 语义 |
|---|---|---|
| runtime_id | str | Runtime ID |
| positions | dict[PositionKey, PositionState] | 多持仓映射 |
| cash | float \| None | 现金 |
| equity | float \| None | 权益 |
| realized_pnl | float | 已实现盈亏 |
| unrealized_pnl | float | 未实现盈亏 |
| updated_ts | int \| None | 更新时间 |
| metadata | dict[str, object] | 扩展信息 |

---

### State 模型升级说明（v0.2）

从本版本开始：

PortfolioState 是持仓状态唯一真实来源（source of truth）。

StateSnapshot 仅用于：

- 导出
- 报表
- 回测输出

禁止：

- 使用 list[PositionState] 作为真实持仓
- 绕过 PositionKey 查找持仓
- 构建第二套持仓状态系统



---

## v0.4 ExecutionResult Partial Fill Migration

本次 migration 新增：

- ExecutionStatus.PARTIALLY_FILLED
- ExecutionStatus.FILLED
- ExecutionResult.filled_quantity
- ExecutionResult.remaining_quantity
- ExecutionResult.avg_fill_price

本次 migration 只修改 Domain 契约，不修改 broker / state / capital 行为。

后续 partial fill 实现必须显式使用 filled_quantity，禁止用 reason / metadata 编码成交数量。
