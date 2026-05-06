# Readmodel / Artifact / Daemon 契约

本文件是专项契约，专门定义 readmodel / artifact / manifest / UI 只读边界。
总架构、三平面、主链与层级边界以 `docs/architecture/structure.md` 为准。
字段、类型、默认值与 Domain 语义以 `docs/domain/domain_contract.md` 为准。

本文档定义观测读模型、UI、artifact、manifest、daemon 的边界。

## 1. 观测读链

标准读链：

```text
DataStore / Artifacts / local_file
→ dashboard_projection / inspect_run / web readmodel
→ web viewmodel
→ UI
```

规则：

- 交易主链是 command plane。
- projection/readmodel 是 query plane。
- projection 是 UI 的权威数据源。
- readmodel 不保证瞬时一致性。
- UI 不直接读 raw lifecycle 来猜业务语义。
- projection 可以折叠展示噪声事件，但不能改 raw event 口径。
- `blocked_by_pending_order` 等刷屏事件可以在 dashboard 展示层折叠，不能从 raw lifecycle 删除。
- code → 中文 label 映射只能发生在 viewmodel/readmodel 展示层，不能改变原始 reason、decision、status、profile、scope 语义。
- readmodel 必须区分 local / dryrun / live。
- UI/dashboard 必须显示运行 scope，不得只显示“成交”“持仓”而不显示来源。
- UI 默认不得合并 local/dryrun/live 的持仓、订单、成交。
- `local_file` 只能作为行情 quote 输入或展示来源，不能被 readmodel 当成 order/fill/position 来源。
- 新读模型默认只读取 `data/store/local`、`data/store/dryrun`、`data/store/live`。
- `inspect_run` 不得把旧 `sandbox` 目录作为正常运行路径读取；旧目录只能在显式 migration/debug 工具中处理。
- readmodel 可以并列展示 local/dryrun/live，但不得把 local/dryrun 的 order、fill、position、snapshot、artifact 汇总成 live 事实。
- live 页面默认只展示 live scope 交易事实；如果展示 local/dryrun，只能作为带 scope 标识的旁路诊断信息。
- projection/readmodel 不得生成交易事实。
- UI 不得生成交易事实。
- UI 不得把 pending/submitted/rejected 展示为真实持仓。
- UI 不得把 dryrun fill 展示为 live broker fact。

## 2. DataStore Event Envelope 读取契约

DataStore event 必须采用：

```text
envelope + domain payload
```

envelope 至少包含：

```text
schema_version
event_id
event_type
runtime_id
runtime_profile
datastore_scope
execution_env
broker_profile
submit_mode
is_live
is_simulated_execution
generated_at
source
payload_type
```

规则：

- profile / scope / source 属于 envelope。
- profile / scope / source 不得进入 domain payload。
- readmodel/projection 必须保留 `runtime_profile`、`datastore_scope`、`event_id`、`source`。
- projection 不得修改 envelope。
- projection 不得把 local/dryrun envelope 转成 live envelope。

## 3. Manifest / Summary 降级

- `manifest` / `current summary` 缺失可以降级。
- manifest、summary、projection schema 损坏不能静默吞掉。
- boot artifact 必须标记 `status=booting`，不能伪装成 running。

## 4. Daemon Artifact

daemon 启动阶段：

- 可以提前写 boot artifact。
- boot artifact 必须 `status=booting`。
- boot artifact 只表达 runtime_id、profile、scope、plan path、plan sha256、expanded/effective plan、空或零值 summary。

运行阶段：

- daemon runner / artifact writer 负责刷新为 `running`、`final` 或 `error`。
- manifest 必须索引 current summary、plan metadata、可选 decision/approved/proposal artifact。
- manifest plan metadata 至少应包含 plan path、plan sha256 和 redacted effective plan config summary。
- manifest 不得写入账号、密码、token、密钥、broker credential、绝对私密路径或环境变量原文。
- artifact 必须带 profile/scope 信息。
- local/dryrun/live artifact 不得混写。
- local/dryrun artifact 不得作为 live manifest、live recovery、live reconciliation 或 live promotion fact 的输入。

读取阶段：

- `inspect_run` 对 manifest 缺失可以降级。
- manifest、summary、projection schema 损坏不能静默吞掉。
- web/readmodel 只能读取 datastore/artifacts，不直接访问 broker/runtime mutation。

推荐 artifact 基础字段：

```json
{
  "schema_version": "...",
  "artifact_type": "...",
  "runtime_id": "...",
  "runtime_profile": "local | dryrun | live",
  "datastore_scope": "local | dryrun | live",
  "is_live": false,
  "is_simulated_execution": true,
  "generated_at": "...",
  "plan": {
    "path": "...",
    "sha256": "...",
    "effective_config_summary": "redacted"
  }
}
```

布尔字段规则：

- `local` artifact 必须 `is_live=false` 且 `is_simulated_execution=true`。
- `dryrun` artifact 必须 `is_live=false` 且 `is_simulated_execution=false`。
- `live` artifact 必须 `is_live=true` 且 `is_simulated_execution=false`。

## 5. Recovery / Idempotency

当前禁止：

- 禁止从 projection 恢复真实持仓。
- 禁止从 lifecycle 推断 position。
- 禁止从 order 推断 fill。
- 禁止从 pending 推断 exposure。
- 禁止从 local snapshot 恢复 live state。
- 禁止从 dryrun artifact 恢复 live state。
- 禁止从 dryrun fill 恢复 live position。
- 禁止从 local/dryrun event envelope 迁移成 live envelope。

未来 recovery / idempotency 强化目标记录在 [production_hardening.md](production_hardening.md)。在未落地并通过 contracts 锁定前，不得把这些目标解释为当前已全部实现能力。

broker reconciliation recovery、full idempotency、advanced recovery/replay 的设计方向是：

```text
broker reconciliation
+ execution records
+ state snapshot
+ explicit runtime profile/scope
```

以下流程应作为生产强化 roadmap 支持幂等：

- fill apply
- order state transition
- snapshot write
- lifecycle append
- projection rebuild
- artifact refresh

目标状态下，重复处理同一 fill/order event 不得重复记仓、重复扣减 cash 或重复计算 pnl。

## 6. 时间语义

系统需要区分：

| 字段 | 语义 |
|---|---|
| `event_time` | 事件真实发生时间 |
| `market_time` | 行情时间 |
| `processing_time` | 系统处理时间 |
| `generated_at` | artifact/projection 生成时间 |
| `received_at` | adapter 或 file producer 接收时间 |

规则：

- Domain 中 `ts` / `bar_ts` 以 `domain_contract.md` 为准。
- adapter 接收到毫秒或微秒时间戳时，必须先归一化，再进入 domain。
- projection 可以保留多个时间维度，但不得混用。
- UI 展示时应避免把 processing time 当 market time。
