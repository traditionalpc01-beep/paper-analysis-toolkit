# Agent Workflow

本文档定义 agent 在当前仓库里的推荐工作顺序，目标是减少“看了很多代码但没有沉淀规则”的情况。

## 1. 默认工作顺序

1. 先读 `AGENTS.md`
2. 再读对应总览文档：
   - 架构问题 -> `docs/ARCHITECTURE.md`
   - pipeline 问题 -> `docs/PIPELINE_STAGES.md`
   - 质量与验收问题 -> `docs/QUALITY_GATES.md`
3. 再读相关实现文件
4. 最后读对应测试

## 2. 每轮改动的推荐闭环

### 小改动

1. 复述现状
2. 写最小计划
3. 修改代码
4. 补测试
5. 更新文档
6. 运行最小验证

### 大改动

1. 先出 execution plan
2. 把大任务拆成多轮可验收子任务
3. 每轮只做一个可关闭子任务
4. 每轮都回写 docs / tests / scripts

## 3. 推荐提示词模板

### 模板 A：先分析，不改代码

```text
请阅读以下文件并输出结构化分析：
1. 当前行为
2. 风险点
3. 最小改造方案
4. 需要补的测试和文档
先不要改代码。
```

### 模板 B：小步实现

```text
请在当前仓库实现一个小步功能，按下面执行：
1. 先阅读相关文件并复述现状
2. 写一个简短实现计划
3. 实现代码
4. 补测试
5. 自查风险和可改进点
6. 给出最终改动说明
```

### 模板 C：复杂需求分阶段

```text
这是一个复杂改动，请先不要写代码。
请输出 execution plan，包含：
1. 目标与范围
2. 受影响模块
3. 分阶段实施步骤
4. 每阶段验收标准
5. 风险与回滚点
```

## 4. 对 agent 最重要的仓库规则

- 先写规则，再写功能
- 先补 tests / checks，再扩大改动面
- 任何新知识尽量回写到 docs，而不是留在聊天记录里
- 不要在 reporter 层推导业务真值
- 复杂逻辑改动优先以测试锁定已有行为

## 5. 本轮新增的固定检查入口

- 文档与约束检查：`scripts/check_agent_harness.py`
- 相关回归：
  - `tests/test_agent_docs.py`
  - `tests/test_quality_contracts.py`
  - `tests/test_agent_harness_check.py`

## 6. 本仓库当前最适合的 agent-first 节奏

1. 先登记 issue
2. 再拆任务
3. 再实现
4. 再用脚本和测试验收
5. 最后关闭 issue
