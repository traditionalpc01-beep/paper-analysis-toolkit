# Agent-Friendly Architecture

## 1. 仓库目标

`paper-analysis-toolkit` 是一个以 `paperinsight` 为核心包的论文分析工具，当前同时支持：
- CLI 工作流：入口在 `paperinsight/cli.py`
- 核心分析链路：主流程在 `paperinsight/core/pipeline.py`
- 桌面桥接：桥接入口在 `paperinsight/desktop_bridge.py`
- 测试与回归：集中在 `tests/`

对 agent 来说，仓库当前最重要的事实不是“功能很多”，而是“链路明确”：
1. 收集 PDF 输入
2. 解析 PDF / Markdown
3. 清洗段落
4. 提取结构化数据
5. 补期刊 / 影响因子
6. 导出 Excel / JSON / 错误日志

## 2. 模块分层

### 2.1 接入层

- `paperinsight/cli.py`
  - 命令入口
  - 环境检查
  - 运行模式选择
  - 用户交互
- `paperinsight/desktop_bridge.py`
  - 桌面端协议输出
  - 运行时配置拼装
  - 面向 UI 的批处理返回结构

### 2.2 编排层

- `paperinsight/core/pipeline.py`
  - 主编排器 `AnalysisPipeline`
  - 串起解析、清洗、提取、补全、导出
  - 控制缓存、错误结构和回退顺序

### 2.3 领域实现层

- `paperinsight/core/extractor.py`
  - 结构化提取
  - regex / LLM 路径选择
- `paperinsight/parser/`
  - PDF 解析入口
  - MinerU / fallback 解析
- `paperinsight/cleaner/section_filter.py`
  - 段落过滤和提取文本裁剪
- `paperinsight/web/journal_resolver.py`
  - 期刊匹配
- `paperinsight/web/impact_factor_fetcher.py`
  - 官方影响因子抓取
- `paperinsight/core/reporter.py`
  - Excel / JSON 导出映射

### 2.4 共享基础设施层

- `paperinsight/models/schemas.py`
  - `PaperData` / `PaperInfo` 等结构
- `paperinsight/utils/config.py`
  - 默认配置
  - 配置兼容迁移
- `paperinsight/utils/config_crypto.py`
  - 敏感字段加解密
- `paperinsight/core/cache.py`
  - Markdown / data cache
- `paperinsight/utils/`
  - 文件重命名、日志、哈希、终端等通用能力

## 3. 运行时主数据流

```text
PDF directory
  -> cli / desktop_bridge
  -> AnalysisPipeline
  -> parser
  -> cleaner
  -> extractor
  -> journal resolver / IF fetchers
  -> reporter
  -> Excel / JSON / error_log
```

## 4. 关键边界

### 4.1 入口边界

- CLI 负责参数、交互、模式选择
- `AnalysisPipeline` 不应该承担新的 CLI 交互职责

### 4.2 结构化边界

- `paperinsight/models/schemas.py` 是结构化事实边界
- 对导出、补全、展示的任何改动，优先确认是否影响 `PaperData`

### 4.3 规则边界

- 期刊匹配与影响因子补全，不是 reporter 决定的
- reporter 只负责“映射与展示”，不负责“推导业务真值”

### 4.4 配置边界

- 运行默认值以 `paperinsight/utils/config.py` 的 `DEFAULT_CONFIG` 为准
- 文档或 UI 展示如与默认值冲突，应优先回到该文件核实

## 5. 外部依赖点

- LLM：由 `paperinsight/core/extractor.py` 所依赖的客户端路径驱动
- MinerU：由 `paperinsight/parser/` 和配置共同决定
- MJL / LetPub / 其他 Web 来源：由 `paperinsight/web/` 下实现控制
- Excel：由 `openpyxl` 输出

这些点是最容易出现“代码变了、文档没跟上”的位置。

## 6. 当前还只部分显式化的知识

以下知识已存在于代码或测试中，但此前缺少总览文档：
- pipeline 各阶段输入输出责任边界
- 报表列顺序和字段稳定性
- 默认配置中哪些字段是行为开关，哪些只是参数
- agent 改动仓库时应该按什么阅读顺序工作

## 7. 本轮最小 harness 改造结果

- 已新增架构图文档：`docs/ARCHITECTURE.md`
- 已新增阶段说明：`docs/PIPELINE_STAGES.md`
- 已新增工作流与门禁文档：
  - `docs/AGENT_WORKFLOW.md`
  - `docs/QUALITY_GATES.md`
  - `docs/KNOWN_GAPS.md`
- 已新增机械检查入口：`scripts/check_agent_harness.py`

## 8. Agent 建议阅读顺序

1. `AGENTS.md`
2. `docs/ARCHITECTURE.md`
3. `docs/PIPELINE_STAGES.md`
4. 相关实现文件
5. `docs/QUALITY_GATES.md`
6. `tests/` 中对应回归
