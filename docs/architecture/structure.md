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

