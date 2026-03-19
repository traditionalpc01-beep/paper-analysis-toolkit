# Agentflow Prepare

本文档记录 agent-first 重构的 Phase 1-4 最小落地形态：先用 MinerU 解析 PDF，产出可供 Trae/Cursor 等 IDE 联网处理的任务目录，再导回期刊与 IF 结果，随后用 Longcat 提取剩余指标，最后导出 Excel。

## 当前范围

- CLI 入口：`paperinsight agent prepare`
- CLI 导入：`paperinsight agent import-identity`
- CLI 指标提取：`paperinsight agent extract-metrics`
- CLI 导出：`paperinsight agent finalize`
- 代码入口：`paperinsight/agentflow/pipeline.py`
- 论文身份线索提取：`paperinsight/agentflow/identity.py`

## Phase 1 输出协议

运行 `paperinsight agent prepare <pdf_dir>` 后，会在 `agent_runs/<run_id>/` 下生成：

- `manifest.json`：本次 run 的总清单
- `papers/<paper_key>/01_parse.md`：MinerU 解析得到的 Markdown
- `papers/<paper_key>/01_parse_meta.json`：解析元数据与错误信息
- `papers/<paper_key>/02_identity_job.json`：供 IDE 联网处理的单篇任务
- `jobs/identity_jobs.jsonl`：批量任务队列
- `jobs/identity_results.jsonl`：后续导回结果的占位文件
- `jobs/identity_prompt.md`：建议直接发给 IDE 的提示说明

## 当前约束

- Phase 1 只负责 `PDF -> Markdown -> identity job`
- Phase 2 只负责 `identity_results.jsonl -> 每篇 identity result / PaperData 兼容 JSON`
- Phase 3 负责 `Markdown -> Longcat 指标提取 -> 合并 identity 结果`
- Phase 4 负责 `03/04 产物合并 -> Excel/JSON 报表`
- 这里不直接调用仓库原有期刊匹配与 IF 抓取逻辑
- `impact_factor_year` 必须由后续联网阶段返回真实年份，不能按当前年份臆造
- 每篇论文的任务文件必须独立，方便一篇一线程处理

## Phase 2 导回协议

运行 `paperinsight agent import-identity <run_dir>` 后，会新增：

- `papers/<paper_key>/03_identity_result.json`：导入并校验后的联网结果
- `papers/<paper_key>/03_paper_data.json`：回写为 `PaperData` 兼容结构的中间产物
- `jobs/identity_import_summary.json`：本次导入统计

`manifest.json` 中每篇论文还会补充：

- `matched`
- `journal_name`
- `impact_factor`
- `impact_factor_year`
- `impact_factor_source`
- `impact_factor_status`

## Phase 3 指标提取协议

运行 `paperinsight agent extract-metrics <run_dir>` 后，会新增：

- `papers/<paper_key>/04_metrics_result.json`：Longcat 提取后、且已合并 identity 信息的 `PaperData`
- `papers/<paper_key>/04_metrics_meta.json`：提取方法、模型、耗时等元信息
- `jobs/metrics_summary.json`：本次指标提取统计

当前合并规则：

- Longcat 负责提取作者、器件结构、EQE、CIE、寿命、优化策略等剩余字段
- 已导回的标题、期刊名、IF、IF 年份、IF 来源、IF 状态优先级更高，合并时覆盖模型结果
- 如果 Longcat 没提到器件，而 identity 中也没有器件，则保持空列表，等待后续 finalize 阶段处理

## Phase 4 最终导出协议

运行 `paperinsight agent finalize <run_dir>` 后，会新增：

- `papers/<paper_key>/05_final_paper_data.json`：最终用于导出的合并结果
- `reports/论文分析报告_<timestamp>.xlsx`：最终 Excel
- `reports/论文分析报告_<timestamp>.json`：可选 JSON 报表
- `jobs/finalize_summary.json`：最终导出统计

当前 finalize 规则：

- 优先使用 `04_metrics_result.json`
- 若存在 `03_paper_data.json`，则其中的标题、期刊名、IF、IF 年份、IF 来源、IF 状态覆盖 `04` 中对应字段
- 若缺少 `04`，则回退使用 `03`
- 若两者都不存在，则该论文以 `incomplete` 状态落入报表

## MinerU API 下载降级

- 针对 MinerU API 返回的 `full_zip_url` 下载阶段，当前已增加有限重试
- 若连续出现 CDN `SSL EOF` 类错误，可自动尝试 `verify=False` 的降级下载
- 该降级仅用于结果包下载，不影响前面的任务创建与状态轮询
