# Structure Contract Freeze Runbook

本 runbook 固化 `futures_v2` 当前结构契约冻结基线。后续生产强化工作必须以这里列出的主链、边界和验证命令为前置约束。

## Frozen Authority Chain

标准链路冻结为：

```text
ExecutionResult
-> Execution Event Translator
-> OrderEvent / FillEvent
-> StateEngine
-> FillApplication (core/state internal)
-> PositionLifecycle / CapitalModel
-> OrderState / PortfolioState / PnLSnapshot
```

确认边界：

- `BrokerAdapter` 只返回 `ExecutionResult`。
- `BrokerAdapter` 不生成 `OrderEvent` / `FillEvent`。
- `ExecutionResult` 不直接进入 `StateEngine`。
- `Execution Event Translator` 是 `OrderEvent` / `FillEvent` production authority。
- `StateEngine` 是 `OrderState` / `PortfolioState` / `PnLSnapshot` mutation authority。
- `Runtime` 不直接写 `PortfolioState` / PnL。
- `FillApplication` 只存在于 `core/state` 内部，不进入 `domain/*`。

## Frozen Docs

- `docs/README.md`
- `docs/runbook/audit_readiness_freeze.md`
- `docs/domain/domain_contract.md`
- `docs/architecture/structure.md`
- `docs/architecture/runtime_profiles.md`
- `docs/architecture/local_runtime.md`
- `docs/architecture/event_state_authority.md`
- `docs/architecture/readmodel_artifacts.md`
- `docs/architecture/testing_guardrails.md`
- `docs/architecture/production_hardening.md`
- `docs/architecture/release_v0_9.md`

## Scope Boundaries

- 不改 `domain/*` 的冻结字段与业务语义。
- 不改 Runtime / Execution canonical 主链。
- 不改 DataStore envelope + payload 格式。
- 不改 contracts 语义。
- 不让 `ExecutionResult` 成为 state mutation 输入。
- 不新增 `StateEngine.apply_execution_result` 或同义外部入口。
- 不让 readmodel/projection/UI 写 state 或 trading event。

## Freeze Check

总控脚本是只读检查入口：

```bash
python tools/run_structure_contract_check.py
python tools/run_structure_contract_check.py --json
```

脚本执行以下检查，任一失败即返回非 0：

- `python -m pytest tests/contracts -q`
- `python -m pytest tests -q`
- `python -m mypy app core adapters optimize web tests`
- `python -m ruff check app core adapters optimize web tests`
- `git diff --check`
- `node --check web/ui/app.js`

脚本不得修改任何文件。`--json` 输出用于 CI 或后续自动化归档；普通输出用于本地人工验收。
