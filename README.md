# PaperInsight CLI

智能科研论文分析工具 - 自动提取 PDF 论文关键信息、补全影响因子并生成排序报告。

当前版本：`2.0.0`

## 这版能做什么

- 扫描目录中的 PDF，支持递归处理
- 优先提取原生文本，失败或明显乱码时再走 OCR 回退
- 支持 PaddleX API (百度 AI Studio)、LLM 语义提取
- 自动补全期刊影响因子，并按 IF 降序生成报告
- 支持多器件参数、数据溯源、错误隔离和缓存复用
- 可选把处理完成的 PDF 重命名为规范格式

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
pip install -e .
```

如果需要额外能力，可选安装：

```bash
# 本地 OCR
pip install paddlepaddle paddleocr

# OpenAI 客户端
pip install openai
```

### 2. 启动引导

首次运行建议按这个顺序：

```bash
paperinsight check
paperinsight config
paperinsight analyze ./pdfs
```

如果你直接运行：

```bash
paperinsight
```

CLI 会显示启动引导，并给出建议命令。

### 3. 配置能力

```bash
paperinsight config
```

配置向导支持：

- PaddleX API（百度 AI Studio）
- LLM（OpenAI / DeepSeek）
- Web 搜索补全影响因子

配置文件默认保存在：`~/.paperinsight/config.yaml`

### 4. 运行分析

```bash
# 分析一个目录
paperinsight analyze ./pdfs

# 递归扫描
paperinsight analyze ./pdfs --recursive

# 强制使用基础正则模式
paperinsight analyze ./pdfs --mode regex

# 启用 API 模式
paperinsight analyze ./pdfs --mode api

# 同时导出 JSON
paperinsight analyze ./pdfs --json

# 处理完成后重命名 PDF
paperinsight analyze ./pdfs --rename-pdfs
```

## 运行模式

### `auto`

默认模式。

- 优先使用已配置的在线能力
- 未配置在线能力时，自动回落到原生文本提取 / 基础正则模式
- 适合大多数场景

### `api`

显式使用智能能力。

- 如果还没配置在线 OCR / LLM，CLI 会先进入配置向导
- 适合追求提取精度的批处理场景

### `regex`

基础模式。

- 不调用 OCR API 或 LLM
- 速度快，适合先试跑
- 对扫描版和复杂版式支持有限

## 输出内容

默认会在输入目录下生成 `输出结果/` 文件夹，包含：

- `Paper_Analysis_Report.xlsx`
- `Paper_Analysis_Report.json`（当使用 `--json` 时）
- `error_log.txt`（当存在失败项时）

Excel 报告按“影响因子”降序排列，主要字段包括：

- 期刊名称
- 影响因子
- 论文标题
- 作者
- 器件结构
- EQE / CIE / 寿命
- 数据溯源
- 优化层级
- 优化策略

## 常用命令

```bash
paperinsight --help
paperinsight analyze --help
paperinsight config
paperinsight check
paperinsight doctor
paperinsight cache-info
paperinsight clear-cache
paperinsight version
```

## 缓存机制

工具默认启用缓存：

- `[MD5]_data.json`：结构化提取结果
- `[MD5]_ocr.txt`：OCR 文本缓存

重复运行时会自动复用缓存，避免重复 OCR 和重复分析。

## 配置文件结构

一个典型的 `~/.paperinsight/config.yaml` 如下：

```yaml
paddlex:
  enabled: false
  token: ""
  model: "PaddleOCR-VL-1.5"
  use_doc_orientation: false
  use_doc_unwarping: false
  use_layout_detection: true
  use_chart_recognition: false
  timeout: 300
  poll_interval: 5

llm:
  enabled: false
  provider: "openai"
  api_key: ""
  model: "gpt-4o"
  base_url: ""
  timeout: 120

web_search:
  enabled: true
  timeout: 30

cache:
  enabled: true
  directory: ".cache"

output:
  format: ["excel"]
  sort_by_if: true
  generate_error_log: true
  rename_pdfs: false
  rename_template: "[{year}_{impact_factor}_{journal}]_{title}.pdf"

pdf:
  max_pages: 0
  text_ratio_threshold: 0.1
```

## 诊断与排错

### 快速检查

```bash
paperinsight check
```

用于检查：

- Python 版本
- 核心依赖
- 网络连接
- 本地 OCR 可用性

### 完整诊断

```bash
paperinsight doctor
```

用于检查：

- 配置文件是否完整
- 在线 API 是否已启用
- 推荐的运行模式

## 文档入口

- [快速开始指南](./使用文档/快速开始指南.md)
- [使用示例](./使用文档/使用示例.md)
- [高级配置说明](./使用文档/高级配置说明.md)
- [常见问题解答](./使用文档/常见问题解答.md)

## 注意事项

- API 模式依赖网络和有效凭证
- 扫描版 PDF 建议至少配置一种 OCR 能力
- 自动提取结果仍建议人工抽样复核
- Web 搜索补全的影响因子可能受网站可用性影响

## 许可证

MIT License
