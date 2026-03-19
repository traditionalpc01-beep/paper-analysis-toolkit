# Agent-First Phase 1 Issues

本文档把当前 1-4 步落地过程拆成可关闭的本地 issue，避免后续继续依赖口头约定。

状态说明：
- `OPEN`：已定义，未完成
- `IN_PROGRESS`：正在实现
- `CLOSED`：已实现并落到仓库

## AH-001 仓库架构地图与入口路由

- 状态：`CLOSED`
- 目标：把当前仓库的入口、模块层次、外部依赖和 agent 阅读顺序沉淀为可复用地图
- 拆分任务：
  - [x] 补充 `docs/ARCHITECTURE.md`
  - [x] 补充 `docs/PIPELINE_STAGES.md`
  - [x] 更新 `AGENTS.md` 路由表，让 agent 能快速定位新增文档
- 关闭证据：
  - `docs/ARCHITECTURE.md`
  - `docs/PIPELINE_STAGES.md`
  - `AGENTS.md`

## AH-002 System of Record 文档底座

- 状态：`CLOSED`
- 目标：把 agent 工作方式、知识来源和缺口记录为仓库内文档，而不是散落在对话里
- 拆分任务：
  - [x] 新建 `docs/AGENT_WORKFLOW.md`
  - [x] 新建 `docs/KNOWN_GAPS.md`
  - [x] 在文档中标出“代码里有、文档里还没有完全固化”的区域
- 关闭证据：
  - `docs/AGENT_WORKFLOW.md`
  - `docs/KNOWN_GAPS.md`

## AH-003 机械化约束与质量门禁

- 状态：`CLOSED`
- 目标：先固化边界和验收口径，再继续扩展功能
- 拆分任务：
  - [x] 新建 `docs/QUALITY_GATES.md`
  - [x] 为报表列顺序、配置默认值、agent 路由增加测试
  - [x] 把第一批需要机械检查的约束写清楚
- 关闭证据：
  - `docs/QUALITY_GATES.md`
  - `tests/test_quality_contracts.py`
  - `tests/test_agent_docs.py`

## AH-004 最小 Harness 与诊断命令

- 状态：`CLOSED`
- 目标：提供可以重复执行的检查入口，减少后续每轮都靠人工回忆
- 拆分任务：
  - [x] 新建 `scripts/check_agent_harness.py`
  - [x] 为检查脚本补测试
  - [x] 把检查项映射回 docs / code / tests
- 关闭证据：
  - `scripts/check_agent_harness.py`
  - `tests/test_agent_harness_check.py`

## AH-005 Codex 八步交互手册

- 状态：`CLOSED`
- 目标：把后续使用 Codex 的推荐交互方式沉淀成单独文档，方便重复使用
- 拆分任务：
  - [x] 新建 `docs/CODEX_AGENT_FIRST_PLAYBOOK.md`
  - [x] 给出每一步的目标、提示词模板、预期产物
- 关闭证据：
  - `docs/CODEX_AGENT_FIRST_PLAYBOOK.md`

## AH-006 Reporter 默认文件名契约不一致

- 状态：`CLOSED`
- 来源：执行 `python -m pytest tests/test_reporting_outputs.py tests/test_desktop_bridge.py -q` 时发现
- 现象：
  - `tests/test_reporting_outputs.py` 期望默认文件名前缀为 `论文分析报告_`
  - `paperinsight/core/reporter.py` 当前实际产出前缀为 `paperinsight_report_`
- 处理结果：
  - [x] 以已有 `README.md` 和测试契约为准，统一默认文件名前缀
  - [x] 更新 `paperinsight/core/reporter.py`
  - [x] 将该契约补进 `docs/QUALITY_GATES.md`
- 关闭证据：
  - `paperinsight/core/reporter.py`
  - `docs/QUALITY_GATES.md`
  - `tests/test_reporting_outputs.py`

## 完成本轮后的默认工作方式

- 新问题先登记到这里或同类 issue 文档，再拆任务
- 复杂改动先出 execution plan，再进入代码实现
- 每轮改动结束后，优先补 docs、tests、script，而不是只停留在代码
