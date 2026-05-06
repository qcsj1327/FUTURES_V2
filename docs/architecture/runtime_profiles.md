# Runtime Profile 契约

本文件是专项契约，专门定义 canonical runtime profile。
总架构、三平面、主链与层级边界以 `docs/architecture/structure.md` 为准。
字段、类型、默认值与 Domain 语义以 `docs/domain/domain_contract.md` 为准。

本文档定义 `futures_v2` 当前三类 canonical runtime profile。Profile 是运行态 / 配置态概念，不是 Domain 字段。

`local` 和 `dryrun` 的最终目的都是保障 `live` 稳定运行。它们用于提前验证主链语义、真实行情、broker adapter、artifact、readmodel 和 UI，不是独立生产目标。

同时，保障 `live` 的前提是数据完全隔离：`local` / `dryrun` 产生的 order、fill、position、snapshot、artifact、projection 不得污染 `live`，不得作为 `live` 的真实持仓、恢复输入、对账依据或晋升事实。

## 1. Profile / Envelope 字段

| 字段 | 归属 | 语义 |
|---|---|---|
| `runtime_profile` | envelope / config / artifact | canonical runtime profile，只允许 `local` / `dryrun` / `live` |
| `datastore_scope` | envelope / datastore / artifact | datastore 隔离 scope，只允许 `local` / `dryrun` / `live` |
| `execution_env` | envelope / runtime config | execution 环境，如 `simulated` / `dryrun` / `live` |
| `broker_profile` | envelope / runtime config | broker adapter profile |
| `submit_mode` | envelope / runtime config | 是否真实提交，`none` / `dryrun` / `live` |
| `is_live` | envelope / artifact / projection | 是否 live scope |
| `is_simulated_execution` | envelope / artifact / projection | 是否使用 local simulated execution |

规则：

- `is_simulated_execution=false` 不等于 live broker fact。
- dryrun 中 `is_simulated_execution=false` 只表示不走 local `SimulatedExecutionEngine`，不表示真实提交或真实交易所成交。
- dryrun order/fill 仍然不是 live broker fact。

## 2. Canonical Profiles

| Profile | 行情输入 | Broker | Execution | 是否真实提交 | Scope | 用途 |
|---|---|---|---|---|---|---|
| `local` | `local_file` | `simulated` | `SimulatedExecutionEngine` | 模拟提交 | `local` | 本地开发、测试、仿真、回放、UI/projection 验证 |
| `dryrun` | `tqkq` | `tqkq` dry-run | dryrun execution fact | 否 | `dryrun` | 真实行情 + 真实 broker adapter + 不提交 |
| `live` | `tqkq` | `tqkq` live submit | live execution fact | 是 | `live` | 真实行情 + 真实提交 |

隔离规则：

- `local` 只写 `local` scope。
- `dryrun` 只写 `dryrun` scope。
- `live` 只写 `live` scope。
- `local` / `dryrun` 数据不得复制、迁移、fallback 或汇总成 `live` 交易事实。
- UI 和 projection 可以并列展示不同 scope，但默认不得合并为单一持仓、成交或权益口径。

## 3. 历史名称与禁止项

当前结构契约不提供 runtime profile 兼容层。旧名称只允许出现在历史名称、迁移说明、禁止项，或用于验证“旧名称被拒绝”的 contract test 中。

禁止作为当前运行入口、plan、datastore scope、artifact scope、测试 fixture 运行模式继续出现：

- `runtime.mode=simulated_v2`
- `runtime.mode=live_file`
- `runtime.mode=tqkq_sim`
- `runtime.mode=tqkq_dryrun`
- `runtime.mode=tqkq_live`
- `runtime.mode=tqkq_live_submit`
- `DEV_START_MODE=live_file`
- `DEV_START_MODE=tqkq_dryrun`
- `DEV_START_MODE=tqkq_live_submit`
- `sandbox` 作为 datastore scope、artifact scope 或 runtime profile

如果某个底层 adapter 或测试还需要模拟行情、文件行情、TQKQ adapter capability，必须通过 `local`、`dryrun`、`live` 的当前 profile 语义进入，或在单元测试中直接构造 adapter fixture；不得重新引入旧 runtime profile。

## 4. local

`local` 是统一模拟调试模式。

目标：低成本验证策略、触发、风控、执行交接、StateEngine、projection/UI，提前发现会影响 `live` 稳定运行的问题。

固定语义：

- 行情源：`local_file`
- broker：`simulated`
- execution：`SimulatedExecutionEngine`
- 是否真实提交：模拟提交
- datastore/artifact scope：`local`
- `is_live=false`
- `is_simulated_execution=true`

允许：

- 读取 `local_file`。
- 模拟下单。
- 模拟提交。
- 更新 local scope 的 `PortfolioState`。
- 生成 local scope 的 order/fill/position/snapshot/event/artifact。
- 复用与 `dryrun` / `live` 相同的 strategy、trigger、portfolio、risk 逻辑。

禁止：

- 连接真实 broker。
- 真实提交订单。
- 直接依赖 live runtime marketdata adapter。
- 在 runtime 内根据交易时段切换行情 adapter。
- 在行情缺失时 silent fallback 到 fake/demo quote。
- 写入 live datastore。
- 生成 live order、live fill、live position 或 live artifact。
- 从 local snapshot 恢复 live state。

## 5. dryrun

`dryrun` 使用真实 TQKQ 行情和真实 TQKQ broker adapter，但 broker submit 必须处于 dry-run 模式。

目标：在不真实提交的前提下验证真实行情、合约映射、委托构造、生命周期、pending、artifact 和 readmodel，作为进入 `live` 前的联调验证层。

固定语义：

- 行情源：`tqkq`
- broker：`tqkq`
- execution：dryrun execution fact
- 是否真实提交：否
- datastore/artifact scope：`dryrun`
- `is_live=false`
- `is_simulated_execution=false`

允许：

- 读取真实 TQKQ 行情。
- 通过 TQKQ broker adapter 验证 handoff、order shape、lifecycle、state transition。
- 产生 dryrun scope 的 order/fill/lifecycle/state/artifact。

禁止：

- 真实提交订单。
- fallback 到 `local_file`。
- fallback 到 simulated broker。
- 使用休盘模拟行情伪装真实行情。
- 将 dry-run order/fill 写成 live broker fact。
- 将 dryrun fill 解释为真实交易所成交。
- 将 dryrun state 作为 live 初始状态或 live reconciliation 输入。
- 将 dryrun artifact 伪装成 live artifact。

## 6. live

`live` 是唯一允许真实提交的模式。

目标：生产运行。`live` 的状态只能来自 `live` scope 的真实提交、真实回报和显式 live recovery，不得被 `local` / `dryrun` 数据污染。

固定语义：

- 行情源：`tqkq`
- broker：`tqkq`
- execution：live execution fact
- 是否真实提交：是
- datastore/artifact scope：`live`
- `is_live=true`
- `is_simulated_execution=false`

必须同时满足：

- profile 为 `live`
- marketdata source 为 `tqkq`
- broker profile 为 `tqkq`
- submit mode 为 `live`
- plan 显式声明 live submit intent
- 启动命令或环境变量显式确认
- artifact/manifest 记录 live confirmation 信息
- datastore namespace、event envelope、artifact manifest 均明确标记 `live` scope

禁止：

- 读取 `local_file` 作为行情源。
- 使用 simulated broker。
- 使用 local simulated quote producer。
- 在行情缺失时 fallback 到模拟行情。
- 将 local/dryrun artifact 伪装成 live artifact。
- 从 local/dryrun datastore 恢复 live state。
