# Plans 配置契约

本目录只保存当前可直接运行的 canonical RunPlan 入口，并且必须对齐 `docs/architecture/*` 的冻结结构契约。

`plans/*.json` 是 profile overlay，不是系统第二套事实源。品种、行情合约、交易合约、默认价格、默认成交量、交易时段等基础配置的唯一入口是 `config/instrument_universe.py`；loader/session builder 按 `runtime.mode` 展开到运行态。

## Canonical Runtime Profiles

当前只允许三个 runtime profile：

| Profile | Plan | 行情源 | Broker | 是否真实提交 | Scope | 用途 |
|---|---|---|---|---|---|---|
| `local` | `plans/dev.local.json` | `local_file` | `simulated` | 模拟提交 | `local` | 本地仿真调试，验证主链、状态、projection、UI |
| `dryrun` | `plans/dev.dryrun.json` | `tqkq` | `tqkq` dry-run | 否 | `dryrun` | 真实行情 + 真实 broker adapter + 不提交 |
| `live` | `plans/dev.live.json` | `tqkq` | `tqkq` live submit | 是 | `live` | 唯一生产实盘运行目标 |

`local` 和 `dryrun` 的最终目的都是保障 `live` 稳定运行。它们可以验证主链语义、策略、风控、订单生命周期、读模型和 UI，但不能污染 `live`。

隔离规则：

- `local` 只写 `local` datastore/artifact scope。
- `dryrun` 只写 `dryrun` datastore/artifact scope。
- `live` 只写 `live` datastore/artifact scope。
- `local` / `dryrun` 的 order、fill、position、snapshot、artifact、projection 不得进入 `live` 持仓、`live` recovery、`live` 对账、`live` promotion fact 或默认合并展示口径。
- UI/projection 可以并列展示 scope，但不得把多个 scope 合成一套交易事实。

## 保留文件

本目录只保留：

- `dev.local.json`
- `dev.dryrun.json`
- `dev.live.json`
- `prices.json`
- `README.md`

不得新增长期 demo plan。能力测试需要特殊配置时，在测试内构造最小 fixture。

## 禁止旧运行名

以下名称不得作为 `runtime.mode`、plan 文件主入口、`DEV_START_MODE`、datastore scope、artifact scope 或测试 fixture 运行模式出现：

- `simulated_v2`
- `live_file`
- `tqkq_sim`
- `tqkq_live`
- `tqkq_dryrun`
- `tqkq_live_submit`
- `sandbox`

旧名称只允许出现在历史 release note、migration 说明，或“旧名称必须被拒绝”的 contract test 中。

## Plan 边界

Plan 可以表达：

- `runtime.mode`
- `runtime` 运行参数，例如 tick 数、TopN、止盈止损比例、默认数量
- profile 所需 adapter 选择
- profile 所需 broker submit mode
- 风控阈值、执行限频、pending 超时等运行参数
- 策略候选及策略参数 overlay
- strategy switch 的初始启用映射

Plan 不得成为以下事实的第二来源：

- 全局基础品种列表
- TQKQ 主连行情订阅映射
- 真实交易合约映射
- local 默认价格和默认成交量
- 交易时段
- 合约规格
- UI/projection 字段语义
- broker 真实成交或持仓事实

如果 plan 中临时出现 `strategies[].symbols`、`strategy_switch.enabled_by_symbol` 或 `roll_policy.contracts`，它们只能是当前迁移期 overlay；最终必须由 loader 按 `config/instrument_universe.py` 展开，不得长期作为独立维护源。

## Strategy Switch / TopN

策略切换是自动晋升流程，不再保留 Web 人工确认/拒绝环节。

标准语义：

- 策略评分事件写入 datastore。
- daemon artifact 刷新时生成 strategy switch proposal。
- 系统根据 `final_score`、成本惩罚、风险惩罚和 TopN 结果自动写入 approved artifact。
- session builder 在下一次显式启动时读取 approved artifact 并装配生效策略。
- 当前运行中的 session 不做热切换。

Plan 中：

- `runtime.active_top_n` 控制参与运行的 TopN 品种数。
- `strategy_switch.approval_required` 必须为 `false`。
- `strategy_switch.min_score` 和 `max_enabled_strategies_per_symbol` 只控制自动晋升阈值，不代表人工审批。

## local prices.json

`prices.json` 只服务 `local` profile 的本地行情输入。

它只承载 marketdata quote，不承载：

- order
- fill
- position
- risk decision
- execution result
- broker account state
- artifact summary

quote 规范：

- key 使用 base symbol，例如 `au`、`ag`。
- 不允许 `*_main` key。
- 顶层保留 `price` / `volume` / `ts`。
- 必须能表达 `symbol`、`instrument_id`、`trade_instrument_id`、`latest_market_price`。
- 必须标明 `quote_source` 与 `is_simulated`。
- 可包含 `bars.5m` / `bars.15m` / `bars.1h` / `bars.1d`。
- bar 字段为 `open` / `high` / `low` / `close` / `volume` / `ts`。

`prices.json` 应由 local quote writer 按统一品种入口生成，不得手工维护第二套默认价格。

## Supported Capabilities Without Standalone Plans

以下能力仍由代码和 focused tests 覆盖，但不再保留独立 demo plan：

- cost model
- halt guard
- order lifecycle
- portfolio risk / sync
- pending guard
- roll policy
- strategy switch / TopN
- TQKQ adapter capability
- partial fill
- local / dryrun / live scope isolation

删除旧 plan 文件不代表删除能力。能力入口必须回到 canonical profile、测试 fixture 或明确的 runtime/service API。

## 校验命令

```bash
python -m tools.validate_plan --config plans/dev.local.json --runtime-id rt_local
python -m tools.validate_plan --config plans/dev.dryrun.json --runtime-id rt_dryrun
python -m tools.validate_plan --config plans/dev.live.json --runtime-id rt_live
```

结构守护应覆盖：

```bash
python -m pytest tests/contracts/runtime_profiles -q
python -m pytest tests/contracts/config -q
python -m pytest tests/contracts/structure -q
```
