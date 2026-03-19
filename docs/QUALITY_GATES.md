# Quality Gates

本文档只写第一批已经适合机械化验证的约束。后续如有新功能，应优先扩展这里，而不是仅扩展口头说明。

## 1. Pipeline 主链路约束

关联文件：
- `paperinsight/core/pipeline.py`
- `paperinsight/parser/base.py`
- `paperinsight/models/schemas.py`

当前门禁：
- pipeline 应维持“缓存 -> 解析 -> 清洗 -> 提取 -> 期刊/IF -> 导出”的主顺序
- 缓存结果必须能重新构造成 `PaperData`
- 解析失败必须落为结构化错误，而不是直接吞掉

当前验证来源：
- `tests/test_v31_features.py`
- `tests/test_prd_regression.py`

## 2. 影响因子约束

关联文件：
- `paperinsight/web/journal_resolver.py`
- `paperinsight/web/impact_factor_fetcher.py`
- `docs/impact_factor_rules.md`

当前门禁：
- 先期刊匹配，再做 IF 补全
- `NO_ACCESS`、`NO_MATCH`、`NOT_VISIBLE`、`ERROR` 不能混用
- IF 值、来源、年份、状态应一起保留

当前验证来源：
- `tests/test_impact_factor_fetcher.py`
- `tests/test_v31_features.py`
- `tests/test_reporting_outputs.py`

## 3. Reporter 约束

关联文件：
- `paperinsight/core/reporter.py`

当前门禁：
- `ReportGenerator.REPORT_COLUMNS` 的字段顺序必须稳定
- 当前固定导出列数为 20
- 默认文件名前缀应保持为 `论文分析报告_<timestamp>`
- reporter 负责展示映射，不负责业务规则推断

当前验证来源：
- `tests/test_reporting_outputs.py`
- `tests/test_quality_contracts.py`

## 4. 配置约束

关联文件：
- `paperinsight/utils/config.py`
- `paperinsight/utils/config_crypto.py`

当前门禁：
- `normalize_config(DEFAULT_CONFIG)` 结果必须保持主要顶层区块
- 当前默认行为应继续满足：
  - `mineru.mode == "api"`
  - `output.format == ["excel"]`
  - `llm.provider == "longcat"`
  - `desktop.engine.mode == "bundled"`

当前验证来源：
- `tests/test_desktop_bridge.py`
- `tests/test_prd_regression.py`
- `tests/test_quality_contracts.py`

## 5. Agent 文档与路由约束

关联文件：
- `AGENTS.md`
- `docs/ARCHITECTURE.md`
- `docs/PIPELINE_STAGES.md`
- `docs/AGENT_WORKFLOW.md`
- `docs/KNOWN_GAPS.md`
- `docs/CODEX_AGENT_FIRST_PLAYBOOK.md`

当前门禁：
- 新增的 agent-first 文档必须存在
- `AGENTS.md` 必须能路由到这些文档
- 文档应至少说明目标、范围或工作方式，而不是只有标题

当前验证来源：
- `tests/test_agent_docs.py`
- `scripts/check_agent_harness.py`

## 6. 最小 harness 入口

统一检查入口：

```bash
python scripts/check_agent_harness.py
```

JSON 输出：

```bash
python scripts/check_agent_harness.py --json
```

## 7. 仍未完全机械化的部分

这些是下一批应继续升级为自动检查的对象：
- pipeline 端到端 golden samples
- docs 与 README 的自动同步校验
- desktop bridge 返回结构的快照测试
- 报表示例文件的 golden diff
