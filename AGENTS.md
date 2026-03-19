# AGENTS Route Table

- 仓库入口与模块分层问题 -> 查看 `README.md`、`docs/ARCHITECTURE.md`
- CLI 入口、命令参数与运行方式 -> 查看 `paperinsight/cli.py`
- 主处理流程、阶段串联与补全顺序 -> 查看 `paperinsight/core/pipeline.py`、`docs/PIPELINE_STAGES.md`
- 数据结构 / Pydantic 校验问题 -> 查看 `docs/schema_pydantic.md`
- 影响因子解析规则（包括 `NO_ACCESS` 处理） -> 查看 `docs/impact_factor_rules.md`
- 期刊匹配与 MJL 解析上下文 -> 查看 `paperinsight/web/journal_resolver.py`
- 影响因子抓取实现与回退来源 -> 查看 `paperinsight/web/impact_factor_fetcher.py`
- 报表字段、导出列与展示映射 -> 查看 `paperinsight/core/reporter.py`、`docs/QUALITY_GATES.md`
- 项目已有工具类与通用辅助能力 -> 查看 `paperinsight/utils/README.md`
- 桌面端桥接、批处理返回结构与 UI 集成 -> 查看 `paperinsight/desktop_bridge.py`
- 配置默认值、配置文件结构与加解密 -> 查看 `paperinsight/utils/config.py`、`paperinsight/utils/config_crypto.py`
- PDF 解析入口与解析结果结构 -> 查看 `paperinsight/parser/`、`paperinsight/parser/base.py`
- 当前 agent-first 改造 issue 与闭环状态 -> 查看 `docs/agent_harness_issues.md`
- Agent 工作约束、交互模板与落地节奏 -> 查看 `docs/AGENT_WORKFLOW.md`、`docs/CODEX_AGENT_FIRST_PLAYBOOK.md`
- 质量门禁、回归约束与检查脚本 -> 查看 `docs/QUALITY_GATES.md`、`scripts/check_agent_harness.py`
- 已知缺口、尚未机械化的知识与风险 -> 查看 `docs/KNOWN_GAPS.md`
- 回归标准、验收样例与边界行为 -> 查看 `tests/`
