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

示例（推荐）：

```json
{ "au": 180.0, "ag": 50.0 }
