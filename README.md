# PaperInsight CLI

基于当前仓库实现整理的论文分析工具说明。本文只写 2026-03-18 在仓库中可以直接核查的事实；历史版本的设计目标请看对应 PRD 文档。

当前版本：`3.0.2`

## 已核实的能力

- 命令行入口由 `paperinsight` 提供，当前可用子命令包括 `analyze`、`config`、`version`、`doctor`、`check`、`cache-info`、`clear-cache`。
- 默认分析链路为：PDF 解析 -> 文本清洗 -> 数据提取 -> 影响因子补全/校正 -> Excel/JSON 导出。
- 当前仓库同时保留两种运行思路：`api` 模式优先启用 LLM/联网能力，`regex` 模式走本地兜底提取。
- 缓存按 PDF 的 MD5 指纹保存，当前缓存文件命名为 `<md5>_data.json`、`<md5>_markdown.md`，并兼容旧版 `<md5>_ocr.md`。
- 默认输出目录是输入 PDF 目录下的 `输出结果/`，默认报告文件名是带时间戳的 `论文分析报告_<YYYYMMDD_HHMMSS>.xlsx`；启用 `--json` 后会额外生成同名前缀的 `.json` 文件。
- 仓库还包含一个 `React + Electron + Python` 的桌面壳，开发命令和 Windows 打包流程分别在 `desktop/package.json` 与 `.github/workflows/` 中可核查。

## 安装

### 基础安装

```bash
git clone https://github.com/traditionalpc01-beep/paper-analysis-toolkit.git
cd paper-analysis-toolkit
pip install -r requirements.txt
pip install -e .
```

### 按能力补充依赖

```bash
# LLM 提取（OpenAI / DeepSeek / Longcat 当前都依赖 openai Python SDK）
pip install openai

# 本地 OCR 兜底
pip install paddlepaddle paddleocr

# MinerU 本地 CLI 解析
pip install mineru

# 实验性 AI 影响因子补全的附加依赖已包含在 requirements.txt / pyproject.toml 中
```

## 推荐启动顺序

```bash
paperinsight check
paperinsight config
paperinsight analyze ./pdfs
```

说明：

- `check` 做快速环境检查。
- `config` 运行交互式配置向导，默认会先引导配置 Longcat，再配置 MinerU。
- `analyze` 会根据参数或当前配置选择 `api` / `regex` 模式。

## 常用命令

```bash
# 默认分析（auto 模式）
paperinsight analyze ./pdfs

# 强制本地兜底模式
paperinsight analyze ./pdfs --mode regex

# 强制 API 模式
paperinsight analyze ./pdfs --mode api

# 递归扫描并额外导出 JSON
paperinsight analyze ./pdfs --recursive --json

# 关闭缓存重跑
paperinsight analyze ./pdfs --no-cache

# 分析完成后重命名 PDF
paperinsight analyze ./pdfs --rename-pdfs

# LLM 开启时导出中英双语字段
paperinsight analyze ./pdfs --bilingual
```

## 输出与报表

默认输出目录：`<PDF目录>/输出结果/`

典型输出文件：

- `论文分析报告_<时间戳>.xlsx`
- `论文分析报告_<时间戳>.json`（仅在 `--json` 或输出格式包含 `json` 时生成）
- `error_log.txt`（仅在有错误时生成）

Excel 当前固定导出 20 列，字段来自 `paperinsight/core/reporter.py::REPORT_COLUMNS`；列级来源说明见 `Excel导出列数据来源说明.md`。

## 配置与安全

- 运行时配置文件路径是 `~/.paperinsight/config.yaml`。
- 运行时默认值来自 `paperinsight/utils/config.py::DEFAULT_CONFIG`；仓库内的 `config/config.example.yaml` 是示例文件，不保证与运行时默认值完全一致。
- 敏感字段会写入本地配置文件前做简单加密/混淆：本地密钥 + XOR + Base64；配置文件和密钥文件都会尝试设置为 `0600` 权限。
- 当前运行时默认值中：`mineru.mode` 为 `api`，`output.format` 为 `['excel']`，`llm.provider` 为 `longcat`。

## 文档索引

- [快速开始指南](./使用文档/快速开始指南.md)
- [高级配置说明](./使用文档/高级配置说明.md)
- [使用示例](./使用文档/使用示例.md)
- [常见问题解答](./使用文档/常见问题解答.md)
- [AI 模型影响因子获取说明](./使用文档/AI模型影响因子获取说明.md)
- [Excel 导出列数据来源说明](./Excel导出列数据来源说明.md)
- [2.0 版本 PRD（归档整理版）](./2.0版本prd.md)
- [3.0 版本 PRD（实现对照版）](./3.0版本prd.md)
- [3.1 版本 PRD（实现对照版）](./3.1版本prd.md)

## 可核查来源

### 仓库内

- `paperinsight/__init__.py`
- `pyproject.toml`
- `requirements.txt`
- `paperinsight/cli.py`
- `paperinsight/core/pipeline.py`
- `paperinsight/core/reporter.py`
- `paperinsight/core/cache.py`
- `paperinsight/utils/config.py`
- `paperinsight/utils/config_crypto.py`
- `desktop/package.json`
- `.github/workflows/build-desktop-windows.yml`
- `.github/workflows/build-windows-package.yml`

### 外部官方文档

- MinerU 官方文档：<https://mineru.net/apiManage/docs>
- MinerU GitHub 仓库：<https://github.com/opendatalab/MinerU>
- Crossref REST API：<https://www.crossref.org/documentation/retrieve-metadata/rest-api/>
- 阿里云 DashScope OpenAI 兼容调用：<https://help.aliyun.com/zh/model-studio/developer-reference/compatibility-of-openai-with-dashscope>
- Moonshot AI Kimi API 快速开始：<https://platform.moonshot.cn/blog/posts/kimi-api-quick-start-guide>
