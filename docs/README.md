# futures_v2 文档入口

本目录按“当前权威规范、历史说明、运维手册、截图资料”分层维护。开发、测试、运维讨论架构边界时，优先阅读当前权威规范，不要从历史 release note 反推当前实现。

## 当前权威契约体系

自 2026-05-07 起：

- `docs/domain/domain_contract.md` 冻结为当前开发与重构的 Domain 字段基线。
- `docs/architecture/structure.md` 冻结为当前开发与重构的架构结构基线。
- `docs/architecture/runtime_profiles.md`、`local_runtime.md`、`event_state_authority.md`、`readmodel_artifacts.md`、`testing_guardrails.md` 是专项契约。
- 后续代码和测试调整必须先满足当前权威契约体系。
- `docs/architecture/production_hardening.md` 是生产强化路线，不作为当前已实现能力验收标准。

权威顺序：

1. `domain/domain_contract.md`：Domain 字段、类型、默认值、enum value、字段语义。
2. `architecture/structure.md`：总架构、三平面、主链、层级职责、全局边界。
3. `architecture/runtime_profiles.md`：`local` / `dryrun` / `live` 专项契约。
4. `architecture/local_runtime.md`：`local_file`、模拟行情、模拟成交、local scope 隔离。
5. `architecture/event_state_authority.md`：event producer authority、StateEngine authority、PortfolioState source of truth。
6. `architecture/readmodel_artifacts.md`：projection/readmodel、artifact/manifest、UI 只读边界。
7. `architecture/testing_guardrails.md`：contracts 测试清单与验证命令。
8. `architecture/production_hardening.md`：生产强化路线，不代表当前全部已落地。
9. `architecture/release_v0_9.md`：历史说明，不作为当前结构契约。

## 当前权威规范

- [架构结构契约](architecture/structure.md)
  - 总架构契约。
  - 定义 command / query / research 三平面、canonical 主链、层级职责、全局边界与禁止越界规则。
  - 专项细节引用各专项契约。

- [Runtime Profile 契约](architecture/runtime_profiles.md)
  - 定义 `local` / `dryrun` / `live` 三类 canonical runtime profile。
  - 明确不提供旧 runtime profile 兼容层。
  - 明确 `local` 为模拟提交，`dryrun` 不真实提交，`live` 真实提交。

- [Local Runtime 契约](architecture/local_runtime.md)
  - 定义 `local_file → local runtime → StrategySet → TriggerEngine → PortfolioEngine → RiskEngine → SimulatedExecutionEngine → SimulatedBroker → StateEngine → local datastore/artifacts`。
  - 定义 `local_file` quote 来源标记、模拟行情与真实快照的隔离。
  - 定义 local 模拟提交 order/fill/scope 隔离规则。

- [Event / State Authority 契约](architecture/event_state_authority.md)
  - 定义 event authority、DataStore envelope、StateEngine mutation authority。
  - 定义持仓、订单、成交、pending 的边界。

- [Readmodel / Artifact / Daemon 契约](architecture/readmodel_artifacts.md)
  - 定义 readmodel、projection、manifest、artifact、UI 只读边界。
  - 定义 recovery 禁止项、artifact redaction、event envelope 读取规则。
  - 未落地 idempotency / recovery roadmap 引用 `production_hardening.md`。

- [Testing Guardrails 契约](architecture/testing_guardrails.md)
  - 定义结构守护、runtime profile 隔离、event/state、projection/artifact 的 contracts 方向。

- [Domain 字段冻结契约](domain/domain_contract.md)
  - `domain/*.py` 字段、类型、默认值、enum value 的冻结说明。
  - 只描述 Domain 数据契约，不描述业务流程。
  - 后续任何 Domain 字段变更必须走 migration。

- [生产强化路线](architecture/production_hardening.md)
  - 记录尚未全部落地的生产级强化目标。
  - 包括对账循环、执行幂等、异步行情、分仓、事件追溯、manifest 增强。
  - 这里是 roadmap，不是当前已实现能力清单。

## 历史说明

- [v0.9 多品种多策略发布说明](architecture/release_v0_9.md)
  - v0.9 阶段历史 release note。
  - 不作为当前架构结构契约。

## 运维手册

- [主链健康检查](runbook/main_health.md)
- [实盘关闭流程](runbook/live_shutdown.md)

## 截图资料

`docs/screenshots/` 保存 dashboard 相关截图，只作为视觉回归和讨论资料，不作为业务事实来源。

## 文档维护规则

- 架构边界改动先更新 `architecture/structure.md` 或对应的 architecture 子契约。
- Domain 字段或 enum 变更必须先更新 `domain/domain_contract.md` 并记录 migration。
- 已实现能力写进结构契约；未实现但计划做的能力写进生产强化路线。
- 历史 release note 不再回改成当前规范。
- 运行模式变更必须先更新 `architecture/runtime_profiles.md`。
- `local_file` 与 local 模拟提交链路变更必须先更新 `architecture/local_runtime.md`。
- event authority、state authority、pending 语义变更必须先更新 `architecture/event_state_authority.md`。
- readmodel、artifact、daemon、manifest、recovery 语义变更必须先更新 `architecture/readmodel_artifacts.md`。
- contracts 和结构守护变更必须先更新 `architecture/testing_guardrails.md`。
- runtime profile、datastore scope、artifact schema、local/live 隔离字段不得加入 Domain dataclass。
- local、dryrun、live 的语义变更不得只写在 release note 中。
