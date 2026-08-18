# Pipeline Stages

本文档只描述当前仓库已经落地的主处理阶段，供 agent 在修改 `paperinsight/core/pipeline.py` 时快速对齐。

## Stage 0: 输入收集

- 入口：
  - `paperinsight/cli.py`
  - `paperinsight/desktop_bridge.py`
- 输入：
  - PDF 目录
  - 运行模式
  - 配置
- 输出：
  - 待处理 PDF 列表
  - 运行时配置
- 不变量：
  - CLI / desktop 负责交互
  - pipeline 只接受确定后的输入

## Stage 1: 缓存判定

- 位置：`paperinsight/core/pipeline.py`
- 输入：
  - PDF 路径
  - MD5
  - cache 开关
- 输出：
  - 命中缓存时直接返回 `PaperData`
  - 未命中则进入解析
- 不变量：
  - cache 命中后仍需能反序列化成 `PaperData`
  - 缓存损坏时不能中断整条链路，应回到重新处理

## Stage 2: PDF 解析

- 位置：
  - `paperinsight/parser/`
  - `paperinsight/parser/base.py`
- 输入：
  - PDF 文件
  - parser 配置
- 输出：
  - `ParseResult`
  - markdown / metadata / error
- 不变量：
  - 失败时必须回传结构化错误
  - parser 不负责业务字段推断

## Stage 3: 文本清洗

- 位置：`paperinsight/cleaner/section_filter.py`
- 输入：
  - parser 产出的 markdown
  - cleaner 配置
- 输出：
  - 供提取使用的清洗文本
  - 关键章节聚合结果
- 不变量：
  - references 等噪声段落应被尽量排除
  - 对指标有帮助的上下文应尽量保留

## Stage 4: 结构化提取

- 位置：`paperinsight/core/extractor.py`
- 输入：
  - markdown_text
  - cleaned_text
  - parse_result.metadata
- 输出：
  - `ExtractionResult`
  - `PaperData`
- 不变量：
  - 结构化真值应进入 schema，而不是散落在自由字典
  - regex / LLM 两条路径都要回到统一结构

## Stage 5: 期刊与影响因子补全

- 位置：
  - `paperinsight/web/journal_resolver.py`
  - `paperinsight/web/impact_factor_fetcher.py`
  - `paperinsight/core/pipeline.py`
- 输入：
  - `PaperData.paper_info`
  - 期刊标题 / ISSN / eISSN
- 输出：
  - 匹配后的期刊元数据
  - 影响因子值、来源、年份、状态
- 不变量：
  - 先解期刊，再补影响因子
  - `NO_ACCESS` 是状态，不等于“没有匹配到”
  - reporter 只能展示状态，不能反推状态

## Stage 6: 导出与错误记录

- 位置：
  - `paperinsight/core/reporter.py`
  - `paperinsight/utils/logger.py`
- 输入：
  - `PaperData` 列表
  - errors 列表
- 输出：
  - Excel
  - JSON（启用时）
  - `error_log.txt`（有错误时）
- 不变量：
  - Excel 报表列顺序必须稳定
  - 输出文件名冲突时需要自动规避

## Stage 7: 批处理汇总

- 位置：
  - `paperinsight/core/pipeline.py`
  - `paperinsight/desktop_bridge.py`
- 输入：
  - 成功结果
  - 错误结果
  - 导出结果
- 输出：
  - CLI 终端摘要
  - desktop bridge 统计对象
- 不变量：
  - 成功项和错误项要能并存
  - UI 统计字段不应直接依赖 Excel 内容回读

## 当前最应该优先守住的阶段契约

1. Stage 4 输出必须可被 schema 和 reporter 同时消费
2. Stage 5 的状态字段必须完整保留到导出层
3. Stage 6 的列顺序和字段映射不能隐式漂移
