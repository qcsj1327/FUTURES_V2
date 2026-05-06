# Audit / Readiness Freeze Runbook

本文档记录阶段 B 的 `AuditService` / `Readiness` 已落地边界。它是结构契约冻结后的补充记录，只描述 sidecar 观测能力，不改变交易主链。

## Phase B Scope

阶段 B 分两步完成：

- B1：新增 audit contracts、`core/services/audit` 最小服务、audit/readiness artifact writer、readmodel 只读入口。
- B2：新增 daemon/orchestration sidecar runner，并以默认关闭方式接入 daemon loop。

阶段 B 没有改变以下主链：

```text
ExecutionResult
-> Execution Event Translator
-> OrderEvent / FillEvent
-> StateEngine
-> OrderState / PortfolioState / PnLSnapshot
```

## Authority Boundary

`AuditService` / `ReadinessChecker` 属于 sidecar / observation / diagnostics 能力，不是 state mutation authority。

固定边界：

- 不修改 `PortfolioState` / PnL / `OrderState`。
- 不生成 `OrderEvent` / `FillEvent`。
- 不调用 `StateEngine` mutation API。
- 不调用 `append_order_event` / `append_fill_event` / `save_portfolio_snapshot`。
- 不作为 recovery mutation。
- 不作为 broker reconciliation mutation。
- 不把 audit alert 转成 runtime control action。
- 所有输出必须保留 `is_source_of_truth=false` 与 `mutation_allowed=false`。

## Runtime Scope

`live` scope 可以输出 `live_audit_observation`。

`local` / `dryrun` 只能输出 diagnostics-only 结果：

- `diagnostic_only=true`
- `is_live=false`
- artifact type 为 `runtime_diagnostics`
- 不得使用 broker reconciliation 命名
- 不得伪装为 live audit artifact

## Daemon Sidecar

daemon 接入点：

- `app/orchestration/audit_runner.py`
- `app/orchestration/daemon_runner.py`
- `scripts/run_daemon.py`

audit 默认关闭。必须显式传入：

```bash
--audit-enabled 1
```

可配置周期：

```bash
--audit-interval-seconds 300
```

sidecar 在 daemon tick/loop 旁路执行。sidecar failure 不得中断交易主链；失败只允许写 degraded readiness artifact 或返回 warning。

critical audit alert 只保留：

```text
suggested_action="suspend_new_trading"
```

它不会自动 suspend trading，也不会修改 runtime control state。

## Artifacts

audit/readiness artifact 固定写入：

```text
data/artifacts/{scope}/audit/
```

文件形态：

```text
audit_{runtime_id}_{ts}.json
readiness_{runtime_id}_{ts}.json
```

artifact 必须包含：

- `schema_version`
- `artifact_type`
- `runtime_id`
- `runtime_profile`
- `datastore_scope`
- `is_live`
- `generated_at`
- `is_source_of_truth=false`
- `mutation_allowed=false`

artifact writer 必须 redacted，不保存 token、password、secret、credential、env 原文。

## Readmodel

`web/readmodel/audit.py` 只读 `data/artifacts/{scope}/audit/`，只返回 scope 匹配 artifact。

readmodel / dashboard projection 只能展示 audit/readiness fragment：

- 不从 audit result 推断 positions。
- 不从 audit result 推断 orders。
- 不从 audit result 推断 fills。
- 不从 audit result 推断 PnL。
- audit alert 合并到 alerts 时必须保留 `source="audit_artifact"`。

## Contracts

阶段 B 新增 contracts 位于：

```text
tests/contracts/audit/
```

覆盖范围：

- AuditService 边界。
- audit scope contract。
- readiness contract。
- artifact scope/redaction contract。
- readmodel readonly contract。
- audit runner sidecar contract。
- daemon audit sidecar contract。

这些 contracts 用来锁定：Audit/Readiness 是 observation / diagnostics，不是 trading event producer、state mutation authority 或 runtime control action。

## Validation Record

阶段 B 收口前已验证以下命令通过：

```bash
pytest tests/contracts/audit -q
pytest tests/contracts -q
pytest tests -q
mypy app core/services/audit web/readmodel tests
ruff check app core/services/audit web/readmodel tests
git diff --check
python tools/run_structure_contract_check.py --json
```

本 runbook 自身的收口验收命令：

```bash
python tools/run_structure_contract_check.py --json
git diff --check
```
