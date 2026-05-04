# Plans 配置说明（RunPlan JSON）

本目录用于存放可直接运行/校验的 plan 配置文件（JSON）。
推荐通过 `tools.validate_plan` 先校验，再用 `scripts.run_plan` 执行。

---

## 快速使用

校验（只解析/展开，不执行）：

```bash
python -m tools.validate_plan --config plans/dev.simulated_v2.json --runtime-id rt_demo
python -m tools.validate_plan --config plans/dev.live_file.json --runtime-id rt_demo
```

## live_file：prices.json 规范（字段语义锁定）

`adapters.market_data.mode = "live_file"` 时，系统从一个 JSON 文件读取最新价：

- 推荐格式：只写 **基础 symbol**（例如 `au`, `ag`）
- 交易/执行层可能会请求 `*_main`（例如 `au_main`），`LiveFileMarketData` 会将其映射到 base symbol 读取
- 文件里只允许 base symbol；出现任何 `*_main` key 都认为数据源污染，直接报错

## runtime.mode

推荐新 plan 只配置 `runtime.mode` 和 `universe.symbols`，其余适配器由总开关联动：

- `simulated_v2`：`adapters.market_data.mode=simulated_v2`，`adapters.broker.mode=simulated`
- `live_file`：`adapters.market_data.mode=live_file`，`adapters.broker.mode=simulated`
- `tqkq_sim`：`adapters.market_data.mode=tqkq`，`adapters.broker.mode=tqkq_sim`

显式填写旧的分散字段时必须与 `runtime.mode` 推导一致，否则 loader 会直接报错并给出冲突字段、期望值、实际值。
`tqkq_sim` 需要本地 `.env` 提供 `TQKQ_USER` / `TQKQ_PASS`，并要求 `instruments.roll_policy.contracts` 使用真实合约，例如 `SHFE.au2406`。

示例：`plans/dev.mode_simulated_v2.json`、`plans/dev.mode_live_file.json`、`plans/dev.mode_tqkq_sim.json`。

## instruments

`instruments.trading_sessions` 以 base symbol 配置交易时段，时间格式为 `HH:MM`。
跨日夜盘用 `start > end` 表达，例如 `21:00-02:30`。

`instruments.roll_policy` 是 `trade_instrument_id` 的唯一来源：

- `mode = "fixed_contract"`：每个 base symbol 固定到 `contracts` 中配置的合约，不自动换月。
- `mode = "fixed_main"`：使用 `contracts` 中当前映射；映射变化时写入 `roll_events.jsonl`。

`universe.symbols` 和 strategy `symbols` 只能写 base symbol，例如 `au`，不能写合约月或 `*_main`。

## runtime Top-N 调度

`runtime.active_top_n` 默认为 `0`，表示不启用，保持全品种执行链路。设置为大于 `0` 时，每个 tick 只允许排名前 N 的 base symbol 进入执行链路，其余品种只更新行情和调度缓存，不写 `order_events.jsonl` / `fill_events.jsonl`。

相关字段：

- `rank_window`：quote 动量/成交量排名窗口，默认 `20`。
- `rank_metric`：`signal_strength` 或 `quote_momentum_volume`，默认 `signal_strength`。
- `rank_refresh_every`：每隔多少 tick 刷新 active symbols，默认 `1`。
- `rank_emit_events`：`1` 时写 `rank_events.jsonl`，供 inspect/web 读取。

示例：`plans/dev.topn.json`。

## strategy switch

运行时会写 `strategy_score_events.jsonl`，每个 tick 记录每个 `(symbol, strategy)` 的确定性 score。
`run_plan` / `run_daemon` 会生成：

`data/artifacts/strategy_switch/strategy_switch_proposal_{runtime_id}.json`

人工确认后执行：

```bash
python -m tools.approve_switch data/artifacts/strategy_switch/strategy_switch_proposal_rt_demo.json \
  --output data/artifacts/strategy_switch/strategy_switch_approved_rt_demo.json
```

同一 `runtime_id` 后续运行会读取 approved artifact，按 symbol 启用确认后的策略集。
示例：`plans/dev.strategy_switch.json`。

## broker 订单生命周期模拟

`adapters.broker.mode` 支持 `simulated` 和 `tqkq_sim`。
`simulated` 的 `params` 默认空对象，保持即时成交。
用于订单跟踪 contracts 时可以配置：

- `fill_delay_ticks`：提交后延迟多少 tick 开始成交，默认 `0`。
- `partial_fill_ratio`：首次部分成交比例，默认 `1.0`。
- `max_ticks_to_fill`：超过该 tick 年龄仍未终态时按 `expired` 写生命周期事件。

示例：`plans/dev.topn_order_lifecycle.json` 会写 `order_lifecycle_events.jsonl`。

`tqkq_sim` 是纸交易 broker，只允许搭配 `runtime.mode=tqkq_sim` / `adapters.market_data.mode=tqkq`。
执行合约来自 `instruments.roll_policy.contracts`，`tq_symbols` 只用于行情订阅。

## instruments.specs 成本模型

`instruments.specs` 可按 base symbol 覆盖内置合约规格，未配置时使用默认表。
允许覆盖字段：`tick_size`、`multiplier`、`margin_rate`、`commission_model`、`slippage_model`。
手续费模式支持 `fixed_per_order`、`per_qty`、`bps_notional`；滑点模式支持 `ticks`、`bps`。
撮合、事件和 replay summary 共用 `core.instruments.cost_model` 的输出。

示例：`plans/dev.cost_model.json`。

## instruments.spec_source（合约规格来源）

`instruments.spec_source` 默认 `"static"`，表示只使用内置默认表 + `instruments.specs` 人工覆盖。

可选 `"tqkq"`：仅当 `adapters.market_data.mode="tqkq"` 时允许启用，会尝试从 TqKq 读取可用字段
并作为低优先级覆盖（初版只拉 `tick_size` / `multiplier`）。`instruments.specs` 人工覆盖始终优先。

示例（推荐）：

```json
{ "au": 180.0, "ag": 50.0 }
