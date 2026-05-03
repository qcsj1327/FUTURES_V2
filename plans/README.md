# Plans 配置说明（RunPlan JSON）

本目录用于存放可直接运行/校验的 plan 配置文件（JSON）。
推荐通过 `tools.validate_plan` 先校验，再用 `scripts.run_plan` 执行。

---

## 快速使用

校验（只解析/展开，不执行）：

```bash
python -m tools.validate_plan --config plans/dev.simulated_v2.json --runtime-id rt_demo
python -m tools.validate_plan --config plans/dev.live_file.json --runtime-id rt_demo

## live_file：prices.json 规范（字段语义锁定）

`adapters.market_data.mode = "live_file"` 时，系统从一个 JSON 文件读取最新价：

- 推荐格式：只写 **基础 symbol**（例如 `au`, `ag`）
- 交易/执行层可能会请求 `*_main`（例如 `au_main`），`LiveFileMarketData` 会将其映射到 base symbol 读取
- 文件里只允许 base symbol；出现任何 `*_main` key 都认为数据源污染，直接报错

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

示例（推荐）：

```json
{ "au": 180.0, "ag": 50.0 }
