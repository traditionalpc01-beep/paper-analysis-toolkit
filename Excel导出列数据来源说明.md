# Excel 导出列数据来源说明

本文只说明当前 Excel 报表中“真正会导出的 20 列”。判断依据来自：

- `paperinsight/core/reporter.py::REPORT_COLUMNS`
- `paperinsight/core/pipeline.py::_generate_reports`
- `paperinsight/models/schemas.py::PaperData.to_excel_row`

## 1. 当前导出列总览

| 序号 | Excel 表头 | 规范字段 | 当前数据来源 |
| --- | --- | --- | --- |
| 1 | 文件名 File | `file` | `pdf_path.name` |
| 2 | 文件地址 URL | `url` | `pdf_path.resolve().as_uri()` |
| 3 | 期刊名称 Journal | `journal` | `paper_info.journal_name`，缺失时回退到匹配期刊名/原始期刊名 |
| 4 | 影响因子 Impact Factor | `impact_factor` | `paper_info.impact_factor` |
| 5 | 作者 Authors | `authors` | `paper_info.authors` |
| 6 | 处理结果/简述 Processing Status | `processing_status` | `_build_processing_summary()` 或 `_build_error_summary()` |
| 7 | 论文标题 Title | `title` | `paper_info.title` |
| 8 | 器件结构 Device Structure | `structure` | `devices[*].structure` 拼接 |
| 9 | EQE(外量子效率) EQE | `eqe` | `devices[*].eqe` 拼接 |
| 10 | 色度坐标 CIE | `cie` | `devices[*].cie` 拼接 |
| 11 | 寿命 Lifetime | `lifetime` | `devices[*].lifetime` 拼接 |
| 12 | 最高EQE Best EQE | `best_eqe` | `paper_info.best_eqe` |
| 13 | 优化层级 Optimization Level | `optimization_level` | `optimization.level` |
| 14 | 优化策略 Strategy Summary | `optimization_strategy` | 优先 `paper_info.optimization_strategy`，缺失时回退 `optimization.strategy` |
| 15 | 优化详情 Optimization Details | `optimization_details` | `optimization.strategy` |
| 16 | 关键发现 Key Findings | `key_findings` | `optimization.key_findings` |
| 17 | EQE原文 EQE Source | `eqe_source` | `data_source.eqe_source` |
| 18 | CIE原文 CIE Source | `cie_source` | `data_source.cie_source` |
| 19 | 寿命原文 Lifetime Source | `lifetime_source` | `data_source.lifetime_source` |
| 20 | 结构原文 Structure Source | `structure_source` | `data_source.structure_source` |

## 2. 各列的具体取值规则

### 2.1 文件名 / 文件地址

这两列不是由 LLM 产生，而是在报告生成阶段由 `AnalysisPipeline._generate_reports()` 直接注入：

- `File` = `pdf_path.name`
- `URL` = `pdf_path.resolve().as_uri()`

### 2.2 期刊名称

`PaperData.to_excel_row()` 当前使用下面的回退顺序：

1. `paper_info.journal_name`
2. `paper_info.matched_journal_title`
3. `paper_info.raw_journal_title`

因此，Excel 里的“期刊名称”可能是：

- LLM / 正则直接提取值
- MJL 解析后的标准化期刊名
- 仅从原文页眉或元数据里抓到的原始标题

### 2.3 影响因子

Excel 不会单独再算一次 IF；它只写出 `paper_info.impact_factor` 当时的最终值。这个值可能来自：

- 原文提取
- MJL profile 接口
- 搜索抓取回退
- WOS Journals API
- 实验性 AI IF 路径
- MJL fetcher 内部的少量硬编码 fallback

是否允许联网结果覆盖原值，取决于 `web_search.correct_existing_impact_factor`。

### 2.4 处理结果/简述

成功行来自 `_build_processing_summary()`：

- 核心字段齐全时：`处理成功：核心字段解析完整`
- 缺失较少时：`处理成功：待补充 ...`
- 缺失较多时：`部分解析异常：缺少 ...`

失败行来自 `_build_error_summary()`：

- 统一格式：`处理失败：<上下文> - <错误信息>`

### 2.5 多器件列

`器件结构`、`EQE`、`CIE`、`寿命` 四列都由 `PaperData.to_excel_row()` 把 `devices` 列表拼成单元格文本：

- 有 `device_label` 时会加前缀，如 `[Champion] 22.5%`
- 多个器件之间用换行符 `\n` 分隔

### 2.6 优化相关列

当前导出规则是：

- `优化层级`：取 `optimization.level`
- `优化策略`：优先取 `paper_info.optimization_strategy`，否则回退到 `optimization.strategy`
- `优化详情`：取 `optimization.strategy`
- `关键发现`：取 `optimization.key_findings`

所以“优化策略”和“优化详情”有可能相同，也有可能前者更短、后者更详细。

### 2.7 原文引用列

四个 `Source` 列都来自 `DataSourceReference`：

- `eqe_source`
- `cie_source`
- `lifetime_source`
- `structure_source`

这些列用于回溯 LLM / 正则在正文中对应到的原句。

## 3. 当前不会导出到 Excel 的内部字段

虽然 `PaperData.to_excel_row()` 里还会生成这些键，但 `ReportGenerator.REPORT_COLUMNS` 当前没有把它们写入 Excel：

- `原始期刊标题`
- `原始ISSN`
- `原始eISSN`
- `匹配期刊`
- `匹配ISSN`
- `匹配方式`
- `期刊主页`
- `影响因子年份`
- `影响因子来源`
- `影响因子状态`

这些字段仍可能出现在中间结果或 JSON 导出里，但不会出现在默认 Excel 列表中。

## 4. 错误行的填充方式

如果某个 PDF 处理失败，`_generate_reports()` 会为它生成一条“错误行”：

- `File`、`URL`、`processing_status` 会被填入
- 其他业务字段全部留空字符串

因此，Excel 中出现大量空列但 `处理结果/简述` 有值时，通常代表该文件进入了错误分支。

## 可核查来源

### 仓库内

- `paperinsight/core/reporter.py`
- `paperinsight/core/pipeline.py`
- `paperinsight/models/schemas.py`
- `tests/test_reporting_outputs.py`
- `tests/test_v31_features.py`

### 外部官方文档

- Clarivate Master Journal List：<https://mjl.clarivate.com/>
- Crossref REST API：<https://www.crossref.org/documentation/retrieve-metadata/rest-api/>
