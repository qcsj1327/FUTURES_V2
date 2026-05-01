# futures_v2 Structure Contract

本文件为上线前结构冻结文档。  
所有新增模块必须符合本文件语义，否则视为越界。

---

## 1. 系统总原则

### 单向主链

MarketData
→ StrategyRegistry
→ StrategyRunner
→ SignalRouter
→ Portfolio
→ Runtime
→ Trigger
→ Risk
→ Execution
→ State

### 核心原则

- 数据只向下游流动
- 上游不依赖下游
- 研究层不进入实盘主链
- Runtime 不生成信号
- Strategy 不执行订单
- core 不读写外部资源
- domain 不包含任何逻辑

---

## 2. domain/

### 职责

domain 是系统唯一数据契约层。

只允许：

- enum
- dataclass
- 类型字段
- 默认值

### 禁止

- 禁止业务逻辑
- 禁止函数式处理
- 禁止读取文件
- 禁止调用 adapters
- 禁止调用 core
- 禁止装配 Runtime
- 禁止 bootstrap 语义

### 当前文件

- enums.py
- feature.py
- market.py
- signal.py
- trigger.py
- risk.py
- execution.py
- event.py
- state.py
- performance.py

---

## 3. adapters/

### 职责

adapters 是外部世界边界。

允许：

- IO
- 文件读写
- broker API
- marketdata API
- storage
- notify

### 禁止

- 禁止交易决策
- 禁止策略逻辑
- 禁止风控逻辑
- 禁止更新核心 State

### 子目录语义

#### adapters/broker/

负责执行接口。

- base.py：BrokerAdapter 接口
- fake_broker.py：测试/占位 broker
- simulated_broker.py：模拟 broker

Broker 只接收 ExecutionOrder，返回 ExecutionResult。

#### adapters/marketdata/

负责行情接口。

- base.py：MarketDataAdapter 接口
- simulated_market_data.py：pull 模式模拟行情

MarketData 不认识 StrategyRegistry。

#### adapters/storage/

负责研究与回测数据 IO。

- csv_signal_loader.py
- csv_report_writer.py

storage 不进入 Runtime 主链。

---

## 4. strategies/

### 职责

strategies 是 alpha / 信号来源层。

输入：

- symbol
- price
- 未来扩展为 FeatureSnapshot / MarketContext

输出：

- SignalDecision
- 未来可扩展为 SignalCandidate

### 禁止

- 禁止下单
- 禁止调用 Execution
- 禁止修改 State
- 禁止调用 Runtime
- 禁止访问 Broker
- 禁止直接读写文件

### 子目录语义

#### strategies/base/strategy.py

策略接口。

#### strategies/base/simple_strategy.py

当前最小策略实现，只用于验证策略接口与主链。

#### strategies/registry.py

策略注册表。

职责：

- register
- get
- all

禁止：

- 不执行策略
- 不排序
- 不裁决
- 不调用 Runtime

#### strategies/breakout/
#### strategies/mean_reversion/
#### strategies/trend_follow/

未来真实策略实现位置。

---

## 5. core/

core 是纯交易业务层。  
不允许 IO，不允许调用 adapters，不允许读取配置文件。

---

## 6. core/strategy_runner/

### 职责

StrategyRunner 负责批量执行策略。

流程：

StrategyRegistry
→ 遍历 strategies
→ strategy.generate(...)
→ list[SignalDecision]

### 禁止

- 不排序
- 不过滤
- 不裁决
- 不风控
- 不下单
- 不改 State

---

## 7. core/signal_router/

### 职责

SignalRouter 负责多信号裁决。

当前 V1 规则：

- 过滤 HOLD
- 返回第一个非 HOLD
- 如果全部 HOLD，则返回 HOLD

### 未来扩展

- confidence 排序
- strength 排序
- 多空冲突处理
- 策略优先级
- 策略权重
- 去重

### 禁止

- 不执行订单
- 不做资金分配
- 不做风控
- 不改 State

---

## 8. core/portfolio/

### 职责

Portfolio 是组合层。

负责：

- 多策略资金分配
- 多品种仓位预算
- 多 runtime 风险资源协调
- 总敞口控制
- 组合级别风险预算

### 当前 V1

PortfolioEngine.allocate(decision) 直接透传 SignalDecision。

这是占位实现，用于固定主链位置。

### 和 Risk 的区别

Portfolio 管整体资源分配。  
Risk 管单笔交易是否允许执行。

### 禁止

- 不生成信号
- 不裁决策略优劣
- 不下单
- 不直接改 State
- 不接 Broker
- 不读 CSV

---

## 9. app/runtime.py

### 职责

Runtime 是执行节点，不是主链入口。

它只执行一个 SignalDecision。

内部链路：

SignalDecision
→ Trigger
→ Risk
→ Execution
→ State

### 允许

- 持有 TriggerEngine
- 持有 RiskEngine
- 持有 ExecutionEngine
- 持有 StateEngine
- 持有 RuntimeConfig
- 持有当前 runtime 的 market/broker adapter 实例

### 禁止

- 不访问 StrategyRegistry
- 不访问 StrategyRunner
- 不访问 SignalRouter
- 不遍历策略
- 不生成信号
- 不读 CSV
- 不做回测分析

---

## 10. app/orchestrator.py

### 职责

Orchestrator 是主链入口胶水层。

它只负责串联：

MarketData
→ StrategyRunner
→ SignalRouter
→ Portfolio
→ Runtime

### 允许

- 取当前行情
- 调 StrategyRunner
- 调 SignalRouter
- 调 Portfolio
- 调 Runtime.run(decision)

### 禁止

- 不写策略逻辑
- 不写风控逻辑
- 不写执行逻辑
- 不更新 State
- 不读写研究报告
- 不直接下单

---

## 11. app/scheduler.py

### 职责

Scheduler 控制运行节奏。

允许：

- run_once
- run_many
- 未来 loop/timer

禁止：

- 不产生信号
- 不裁决信号
- 不做风控
- 不下单

---

## 12. app/runtime_registry.py

### 职责

管理多个 Runtime。

用于：

- 多品种
- 多策略组合
- 多 runtime 实例

禁止：

- 不执行策略
- 不做信号裁决
- 不直接交易

---

## 13. app/scheduler_registry.py

### 职责

批量调度多个 Runtime。

禁止：

- 不做策略逻辑
- 不做组合逻辑
- 不直接操作 State

---

## 14. research/

### 职责

research 是研究 / 回测 / 分析层。

允许：

- replay
- batch replay
- report analyzer
- run report
- CSV 驱动回测
- 批量实验

### 禁止

- 不进入 live 主链
- 不被 app/runtime 调用
- 不直接修改 live 配置
- 不写 broker 逻辑

### 当前文件

- replay.py
- batch_replay.py
- report_analyzer.py
- run_report.py

---

## 15. optimize/

### 职责

optimize 是自动调参、自我学习、晋升层。

工作流：

research 回测
→ optimize/evaluator 评估
→ optimize/tuner 生成候选参数
→ optimize/selector 选择候选
→ optimize/promoter 晋升
→ optimize/registry 固化参数
→ app 使用已批准参数运行

### 子目录语义

#### optimize/evaluator/

评估策略表现：

- 收益
- 回撤
- 胜率
- 稳定性
- 交易频率
- 风险指标

#### optimize/tuner/

生成候选参数：

- 网格搜索
- 随机搜索
- 贝叶斯优化
- 遗传算法

#### optimize/selector/

从候选中筛选稳健参数。

#### optimize/promoter/

晋升流程：

candidate
→ backtest_passed
→ paper_passed
→ human_approved
→ live_active

#### optimize/registry/

保存参数版本。

#### optimize/scheduler/

定期调优任务。

### 绝对禁止

- 不允许 candidate 直接进入 live
- 不允许 strategy 自己改参数
- 不允许 runtime 自动改参数
- 不允许 live 自动切换未批准参数

---

## 16. config/

### 职责

配置层。

未来放：

- RuntimeConfig 文件加载
- 策略参数配置
- 环境配置
- live/paper/replay 模式配置

禁止：

- 不写交易逻辑
- 不写策略逻辑

---

## 17. bootstrap/

### 职责

系统装配层。

未来负责：

- 根据 config 构建 adapters
- 根据 config 构建 Runtime
- 根据 config 构建 StrategyRegistry
- 根据模式选择 replay/paper/live

禁止：

- 不写策略
- 不写风控
- 不写执行逻辑

---

## 18. scripts/

### 职责

人工开发工具脚本。

允许：

- 临时验证
- 本地调试
- 手动运行

禁止：

- 不作为生产入口
- 不被核心代码依赖

---

## 19. data/

### 职责

数据文件目录。

包含：

- raw
- replay
- reports
- state
- cache
- artifacts

禁止：

- 不放 Python package
- 不放业务代码

---

## 20. docs/

### 职责

文档目录。

包含：

- architecture
- domain
- runtime
- strategy
- optimize
- runbook
- decisions

禁止：

- 不放 Python package

---

## 21. logs/

日志输出目录。

禁止提交真实运行日志。

---

## 22. web/

### 职责

未来可视化层。

允许：

- dashboard
- api
- ws
- viewmodels

禁止：

- 不做交易决策
- 不直接下单
- 不直接改 State

---

## 23. tools/

工具目录。

用于离线工具，不进入主链。

---

## 24. utils/

通用工具目录。

必须谨慎使用。  
禁止放业务语义。

---

## 25. tests/

### 职责

测试层。

当前优先级：

1. contracts
2. unit
3. integration
4. replay
5. regression
6. strategies

### contracts/

锁结构、字段、主链语义。

### unit/

锁局部行为。

### integration/

锁跨模块流程。

### replay/

锁回测流程。

### regression/

锁历史问题不复发。

---

## 26. 上线模式

### replay

由 research 驱动。

使用：

- CSV signal
- ReplayRunner
- BatchReplayRunner
- report analyzer

### paper

使用：

- simulated market
- simulated broker
- orchestrator
- scheduler

### live

使用：

- real market adapter
- real broker adapter
- explicit config
- human-approved params

---

## 27. 上线前绝对禁止

- Runtime 调用 StrategyRegistry
- Runtime 调用 StrategyRunner
- Runtime 调用 SignalRouter
- Strategy 调用 Runtime
- Strategy 调用 Execution
- Strategy 修改 State
- SignalRouter 调用 Risk
- SignalRouter 调用 Execution
- Portfolio 下单
- Portfolio 修改 State
- core 读写文件
- domain 写逻辑
- research 被 live 主链调用
- optimize 自动修改 live 参数
- live 使用 simulated broker
- live 使用 simulated market
- 未批准参数进入 live

---

## 28. 最终主链冻结

上线前主链必须保持：

MarketData
→ Orchestrator
→ StrategyRegistry
→ StrategyRunner
→ strategies
→ SignalRouter
→ Portfolio
→ Runtime
→ Trigger
→ Risk
→ Execution
→ State

其中：

- Orchestrator 是入口
- Runtime 是执行节点
- StrategyRegistry 是策略容器
- StrategyRunner 是策略执行器
- SignalRouter 是信号裁决器
- Portfolio 是组合资源分配器
- Risk 是单笔风控
- Execution 是订单执行调度
- State 是状态记录


---

## 主链歧义消除规则

从本阶段开始，禁止“最小兼容式修补”掩盖主链语义问题。

主链必须按根因解决，而不是通过默认值、兜底字符串或 silent fallback 掩盖问题。

---

## 标准主链（唯一合法执行路径）

MarketData
→ StrategyRegistry
→ StrategyRunner
→ SignalRouter
→ TriggerEngine
→ RiskEngine
→ ExecutionEngine
→ StateEngine

---

## 各层职责（强约束）

### StrategyRunner

- 只负责：
  - 调用 strategy.generate
  - 产出 SignalCandidate / SignalDecision

- 禁止：
  - 修改 signal 字段
  - 注入默认值

---

### SignalRouter

- 只负责：
  - 多策略选择

- 禁止：
  - 修复字段
  - 填充 instrument_id
  - 修改 ts / price / side

---

### TriggerEngine

- 必须保证：
  - TriggerResult 是“结构完整”的

- 禁止：
  - 产生 None 的 instrument_id / trade_instrument_id

- 如果缺失：
  - 必须标记 lifecycle = BLOCKED
  - 并携带 reason

---

### RiskEngine（关键约束）

这是第一层允许“拒绝”的地方，但不是“修复”的地方

必须：

- 不允许使用 fallback：
  instrument_id or ""
  trade_instrument_id or ""

- 不允许覆盖上游 reason（除非是本层新错误）

规则：

- trigger 未触发 → allowed = False（保留原 reason）
- 字段缺失 → allowed = False（明确 reason）
- 数量非法 → allowed = False（明确 reason）

禁止：

- fallback string
- silent 修复
- 吞掉错误原因

---

### ExecutionEngine

- 只执行：
  - 已经通过 Risk 的决策

- 禁止：
  - 再做风控判断
  - 修改 quantity / side

---

### StateEngine

- 只负责：
  - 状态落地

- 禁止：
  - 推断业务逻辑
  - 修改决策

---

## 全链路原则（必须遵守）

### 1. 不允许 fallback 修复

禁止：

x or ""
x or 0

---

### 2. 不允许吞错误

必须：

- 保留原始 reason
- 或追加明确 reason

禁止：

reason = "unknown"

---

### 3. 不允许跨层修复

错误必须在产生的那一层解决

禁止：

- Trigger 的错误 → Risk 修
- Risk 的错误 → Execution 修

---

### 4. 数据必须“显式正确”，而不是“可运行”

优先级：

正确性 > 可运行性 > 兼容性

---

## 结论

主链是系统的“物理定律”，不是“尽量跑通”。

从此以后：

- 不允许最小修复
- 不允许 silent fallback
- 不允许默认填充掩盖错误

所有问题必须在源头解决。


---

## Orchestrator / Runtime 边界规则

Orchestrator 只负责策略侧编排：

\`\`\`text
MarketData
→ StrategyRunner
→ SignalRouter
→ Runtime.run(decision)
\`\`\`

Runtime 负责交易主链执行：

\`\`\`text
TriggerEngine
→ PortfolioEngine
→ RiskEngine
→ ExecutionEngine
→ StateEngine
\`\`\`

强约束：

- Orchestrator 不直接持有 PortfolioEngine
- Orchestrator 不直接调用 Risk / Execution / State
- PortfolioEngine 必须挂在 Runtime 内
- Runtime 是唯一合法的交易主链执行入口

禁止：

- 在 Orchestrator 中绕过 Runtime 调用 Portfolio / Risk / Execution / State
- 在 Orchestrator 中注入 quantity
- 在 Orchestrator 中修复 signal 字段

---

## PortfolioState 多仓位状态模型

从 v0.1-core-locked 之后，状态层开始支持多仓位结构。

### 状态对象职责

PositionKey

= instrument_id + trade_instrument_id + position_side

PositionState

= 单个持仓快照

PortfolioState

= 多持仓容器

### 强约束

- PositionKey 是唯一持仓身份

- 多空方向必须由 position_side 区分

- PositionState 只表示单个持仓

- PortfolioState 只负责容纳多持仓状态

- 本阶段不允许引入 PnL 计算逻辑

- 本阶段不允许引入加仓 / 平仓逻辑

- 本阶段不允许改主链执行顺序

---

## Domain Freeze 修正规则：v0.2 State Domain Migration

v0.1-core-locked 冻结的是主链 Domain：

- SignalDecision
- TriggerResult
- RiskDecision
- ExecutionOrder
- ExecutionResult

这些结构不允许顺手新增字段、不允许改字段语义、不允许改 enum value。

本阶段新增：

- PositionKey
- PortfolioState

属于显式状态层 Domain Migration，不是主链 Domain 修改。

### 新增状态层 Domain

PositionKey
= instrument_id + trade_instrument_id + position_side

PortfolioState
= runtime_id + dict[PositionKey, PositionState]

### Source of Truth

从本阶段开始：

PortfolioState 是持仓状态唯一真实来源。
StateSnapshot 仅用于导出、报表、回测输出。

禁止：

- StateSnapshot 参与主链状态更新
- list[PositionState] 作为真实持仓存储
- 绕过 PositionKey 直接查找持仓
- 新增第二套持仓状态模型

### Frozen / Mutable 边界

不可变：

- PositionKey
- PortfolioState

可变：

- OrderState
- PositionState
- StrategyState
- SystemState
- StateSnapshot

原因：

事件 / 决策对象应不可变。
状态对象允许被 StateEngine 更新。
PortfolioState 容器身份不可变，但内部 positions 承载真实状态映射。

### 后续规则

从本次 migration 提交后：

- 不再新增 state domain 字段
- 不再新增 PortfolioState 字段
- 不再修改 PositionKey 语义
- 不再修改 PositionState 字段语义
- 如必须继续改 state domain，必须新开 Domain Migration

---

## StateEngine 与 PositionLifecycle 职责分离（v0.3）

### StateEngine（编排层）

职责：

- 接收 ExecutionOrder / ExecutionResult
- 生成 OrderEvent
- 管理 PortfolioState 容器
- 维护 positions 映射（PositionKey → PositionState）

禁止：

- 不允许写交易逻辑（加仓 / 平仓 / pnl）
- 不允许直接修改 PositionState 计算字段
- 不允许实现价格 / 数量计算

---

### PositionLifecycle（业务语义层）

职责：

- 定义持仓演化规则：
  - 开仓
  - 加仓
  - 减仓
  - 清仓
- 计算：
  - avg_price
  - realized_pnl
- 校验：
  - 数量合法性
  - 平仓边界
  - 无仓平仓

禁止：

- 不允许访问 PortfolioState
- 不允许生成 Event
- 不允许管理多个 position（只处理单 key）

---

### 分层原则

StateEngine = orchestration（控制流）
PositionLifecycle = business semantics（交易语义）

禁止回退为：

StateEngine 同时负责：
- orchestration
- business logic ❌

---

### 未来扩展位置

- capital model → 新模块（不放入 lifecycle）
- fee / slippage → execution 层
- risk limit → risk 层


---

## Risk / State / Capital / Exit 职责边界审计结论

### RiskEngine

职责：

- 编排风险规则
- 调用 PositionLimit
- 调用 RiskBudget
- 输出 RiskDecision

禁止：

- 修改 PortfolioState
- 修改 cash / equity
- 直接计算持仓 PnL
- 生成 ExecutionOrder

### RiskBudget

职责：

- 读取 portfolio.cash / equity
- 根据 risk_budget、price、stop_loss_distance 调整 quantity

允许：

- 读取 cash
- 下调 quantity

禁止：

- 增加 quantity
- 修改 cash
- 修改 PortfolioState

### PositionLimit

职责：

- 基于 PortfolioState.positions 判断是否超过最大持仓

允许：

- 读取 PositionKey / PositionState

禁止：

- 修改 position
- 修改 portfolio
- 修改 quantity

### CapitalModel

职责：

- 维护 cash
- 维护基础 equity
- 判断 insufficient_cash

禁止：

- 判断交易方向是否允许
- 修改 position lifecycle
- 生成风险决策

说明：

当前 equity 为简化模型：

equity = cash + position.quantity * position.avg_price

后续如需 mark-to-market，必须引入 current_price，并单独提交。

### StateEngine

职责：

- 编排 State 更新
- 维护 PortfolioState
- 写入 PositionKey → PositionState
- 调用 PositionLifecycle
- 调用 CapitalModel
- 提供 create_exit_order 接口

禁止：

- 直接计算 avg_price
- 直接计算 realized_pnl
- 直接计算 cash_delta
- 递归执行 exit order

### PositionLifecycle

职责：

- 开仓
- 加仓
- 减仓
- 清仓
- 计算 avg_price
- 计算 realized_pnl

禁止：

- 访问 PortfolioState
- 修改 cash
- 生成 OrderEvent
- 生成 ExitOrder

### ExitRules

职责：

- 判断 stop_loss / take_profit 是否触发

禁止：

- 生成订单
- 修改 position
- 修改 portfolio

### ExitOrderFactory

职责：

- 把 ExitSignal + PositionState 转换为平仓 ExecutionOrder

禁止：

- 执行订单
- 修改 State
- 判断价格条件


---

## Exit 职责迁移：State → Trade Service

从本阶段开始，Exit 相关职责从 `core/state` 迁移到 `core/services/trade`。

### core/state

职责：

- PortfolioState 更新
- PositionLifecycle 调用
- CapitalModel 调用
- OrderEvent 生成

禁止：

- 判断 exit 条件
- 生成 exit order
- 编排 exit 服务

### core/services/trade

职责：

- ExitRules：判断 stop_loss / take_profit
- ExitOrderFactory：生成平仓 ExecutionOrder
- ExitService：组合 ExitRules 与 ExitOrderFactory

禁止：

- 修改 PortfolioState
- 执行订单
- 修改 cash / equity
- 计算 pnl

### Runtime

职责：

- 在 market loop 中调用 ExitService
- 如生成 exit order，则交给 broker 执行
- 执行结果再交回 StateEngine.apply


---

## Portfolio-level Risk 职责边界

组合级风控从本阶段开始放入 `core/risk/portfolio_limit.py`。

### PortfolioLimit

职责：

- 基于 PortfolioState 读取组合总敞口
- 限制 max_total_exposure
- 限制 max_active_symbols
- 只返回拒绝原因，不修改 PortfolioState

允许：

- 读取 PortfolioState.positions
- 读取 PositionState.quantity / avg_price
- 读取 TriggerResult.instrument_id

禁止：

- 修改 position
- 修改 portfolio
- 修改 cash / equity
- 修改 quantity

### RiskEngine

职责：

- 编排 PositionLimit / RiskBudget / PortfolioLimit
- 输出 RiskDecision

禁止：

- 直接计算组合敞口
- 直接维护 active symbols
- 修改 PortfolioState

---

## State 子模块职责边界：CapitalModel 与 MarkToMarket

### StateEngine

职责：

- 接收 ExecutionOrder / ExecutionResult
- 生成 OrderEvent
- 调用 PositionLifecycle
- 调用 CapitalModel
- 写入 PortfolioState.positions

禁止：

- 计算 avg_price
- 计算 realized_pnl
- 计算 market_value
- 计算 unrealized_pnl
- 执行 mark-to-market

### PositionLifecycle

职责：

- 开仓
- 加仓
- 减仓
- 清仓
- 计算 avg_price
- 计算 realized_pnl

禁止：

- 修改 cash
- 修改 equity
- 执行 mark-to-market
- 访问整个 PortfolioState

### CapitalModel

职责：

- 处理成交后的 cash 变化
- 处理 commission
- 判断 insufficient_cash
- 维护基础 equity

禁止：

- 使用 current_price
- 计算 unrealized_pnl
- 执行 mark-to-market
- 修改 PositionState

### MarkToMarket

职责：

- 使用 current_price 对 PortfolioState 估值
- 计算 market_value
- 计算 unrealized_pnl
- 计算 mark-to-market equity

禁止：

- 修改 cash
- 修改 PortfolioState
- 修改 PositionState
- 生成订单
- 生成风险决策

### 估值原则

CapitalModel 处理“成交发生后的资金变化”。

MarkToMarket 处理“行情变化后的账户估值”。

二者禁止合并。

