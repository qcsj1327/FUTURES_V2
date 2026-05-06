# Local Runtime 契约

本文件是专项契约，专门定义 local / local_file / simulated execution 边界。
总架构、三平面、主链与层级边界以 `docs/architecture/structure.md` 为准。
字段、类型、默认值与 Domain 语义以 `docs/domain/domain_contract.md` 为准。

`local` 是 futures_v2 的统一模拟调试模式。它可以使用真实行情快照或模拟行情写入的 `local_file`，但执行侧必须始终走模拟提交，并且所有交易事实只能落入 local scope。

## 1. 标准链路

```text
local_file
→ local runtime
→ StrategySet
→ TriggerEngine
→ PortfolioEngine
→ RiskEngine
→ SimulatedExecutionEngine
→ SimulatedBroker
→ StateEngine
→ local datastore/artifacts
```

如果主链实现中存在 Signal Router、Execution Handoff、Execution Event Translator 等中间组件，`local` 也必须复用同一条主链，不得走本地专用旁路。

完整链路语义：

```text
local_file
→ local runtime
→ StrategySet
→ Signal Router
→ TriggerEngine
→ PortfolioEngine
→ RiskEngine
→ Execution Handoff
→ SimulatedExecutionEngine
→ SimulatedBroker
→ ExecutionResult
→ Execution Event Translator
→ OrderEvent / FillEvent
→ StateEngine
→ local OrderState / PortfolioState / PnLSnapshot
→ local datastore/artifacts
```

## 2. local_file

`local_file` 是 `local` runtime 的唯一行情输入。

`local_file` 可以由两类 producer 写入：

1. 实盘交易时间：
   - TQKQ snapshot writer 把真实行情快照写入 `local_file`。
   - `local` runtime 只读取该文件，不直接连接 TQKQ marketdata adapter。

2. 休盘时间：
   - local simulated quote producer 仿真实盘行情结构。
   - 模拟行情继续写入同一个 `local_file`。
   - `local` runtime 仍只读取该文件。
   - 品种、合约、默认价格和默认成交量必须来自 `config/instrument_universe.py`。

`local_file` 只能包含 marketdata quote，不得包含：

- order
- fill
- position
- risk decision
- execution result
- broker account state
- artifact summary

## 3. Quote 来源标记

`local_file` 中的 quote 必须显式标记来源：

```text
quote_source = tqkq_snapshot | local_simulated
is_simulated = true | false
```

推荐字段：

```text
symbol
instrument_id
trade_instrument_id
latest_market_price
volume
open_interest
market_time
received_at
generated_at
trading_date
market_phase
source_session
quote_source
is_simulated
```

规则：

- `quote_source=tqkq_snapshot` 表示来自真实行情采集。
- `quote_source=local_simulated` 表示来自休盘模拟行情。
- `is_simulated=true` 必须只出现在模拟行情。
- `is_simulated=false` 必须只出现在真实采集行情。
- 模拟行情不得伪装成真实行情。
- 真实行情缺失时不得用模拟行情静默补洞。
- 模拟行情不得覆盖同一时间戳的真实行情。
- UI/projection 不得根据字段缺失自行猜测行情来源。

## 4. 模拟提交隔离

`local` 模式允许模拟提交，但所有交易事实必须属于 local/simulated scope。

local order/fill/lifecycle event 的 envelope、datastore namespace 或 artifact metadata 必须显式包含：

```text
runtime_profile = local
execution_env = simulated
broker_profile = simulated
submit_mode = none
datastore_scope = local
is_live = false
is_simulated_execution = true
```

local 模拟订单 ID 必须带 local/simulated 前缀，例如：

```text
LOCAL-SIM-...
```

local 模拟成交回报 ID 必须带 local/simulated 前缀，例如：

```text
LOCAL-FILL-...
```

禁止：

- local 生成真实 broker order id。
- local 生成真实 broker fill id。
- local order/fill 被 projection 当作 live broker fact。
- local facts 进入 live projection。
- local facts 进入 live promotion。
- local facts 进入 live recovery。
- local order/fill/position/artifact 离开 local scope。
- local position 进入 live portfolio。
- UI 默认合并 local/live 持仓。
- recovery 从 local snapshot 恢复 live state。
- local simulated quote producer 被写成 runtime profile 或 canonical mode。
