# Known Gaps

本文档记录“当前仓库里重要，但还没有完全机械化或完全文档化”的部分，避免后续重复踩坑。

## 1. 仍偏依赖代码阅读的知识

- `paperinsight/core/extractor.py` 中 regex 和 LLM 的具体分支策略
- `paperinsight/core/pipeline.py` 中不同 Web fallback 的细节串联
- `paperinsight/desktop_bridge.py` 面向前端的返回结构演进
- parser 层对不同 PDF 情况的实际降级路径

## 2. 当前文档已补，但还没形成强校验的区域

- `docs/ARCHITECTURE.md` 里的模块分层还没有自动和目录结构对齐校验
- `docs/PIPELINE_STAGES.md` 只覆盖主链路，还没有覆盖所有分支和异常路径
- `docs/AGENT_WORKFLOW.md` 目前更多是团队约定，尚未完全转成 CI 规则

## 3. 下一批最值得继续做的 harness

1. 为 `AnalysisPipeline` 增加更稳定的端到端样例
2. 为报表导出增加 golden file 对比
3. 为 desktop bridge 增加更完整的协议快照测试
4. 为文档新增“代码引用存在性”自动检查

## 4. 容易产生 AI slop 的位置

- 直接在 reporter 中补业务规则
- 在多个文档里复制默认配置，但没有指回 `DEFAULT_CONFIG`
- 修改影响因子状态语义时只改文档或只改测试，未同时改实现
- 大需求一次性改太多文件，缺少阶段性验收点

## 5. 推荐的后续处理方式

- 新需求先写 issue 拆分
- 大改动先写 plan
- 每轮合并前先跑：
  - `python scripts/check_agent_harness.py`
  - 相关 `pytest` 子集
