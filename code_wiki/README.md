# PaperInsight Code Wiki 文档索引

本 Code Wiki 文档集提供了 PaperInsight 项目的完整技术文档，帮助开发者快速了解项目架构、模块职责、关键实现和使用方式。

---

## 文档列表

| 序号 | 文档名称 | 说明 |
|------|----------|------|
| 01 | [项目架构](./01-项目架构.md) | 项目整体架构、技术栈、目录结构和核心处理流程 |
| 02 | [模块职责](./02-模块职责.md) | 各模块的职责、功能和相互关系 |
| 03 | [关键类与函数](./03-关键类与函数.md) | 核心类、函数的详细说明和使用示例 |
| 04 | [依赖关系](./04-依赖关系.md) | Python 依赖、Node.js 依赖和外部服务依赖 |
| 05 | [运行指南](./05-运行指南.md) | 安装、配置和运行的完整指南 |
| 06 | [发展方向](./06-发展方向.md) | 项目未来发展方向和改进建议 |

---

## 快速导航

### 我想了解项目整体情况
→ 阅读 [01-项目架构](./01-项目架构.md)

### 我想了解各模块的功能
→ 阅读 [02-模块职责](./02-模块职责.md)

### 我想了解核心代码实现
→ 阅读 [03-关键类与函数](./03-关键类与函数.md)

### 我想了解项目依赖
→ 阅读 [04-依赖关系](./04-依赖关系.md)

### 我想运行项目
→ 阅读 [05-运行指南](./05-运行指南.md)

### 我想了解项目未来规划
→ 阅读 [06-发展方向](./06-发展方向.md)

---

## 项目概述

**PaperInsight** 是一个智能科研论文分析工具，专注于从 PDF 格式的学术论文中提取结构化数据。

### 核心特性

- **智能解析**: 使用 MinerU 高性能 PDF 解析
- **语义提取**: 支持多种 LLM 提供商（OpenAI、DeepSeek、文心一言、Longcat）
- **数据验证**: Pydantic 模型严格校验
- **影响因子**: 多数据源交叉验证
- **双模式**: API 模式和 Regex 模式互为补充
- **缓存机制**: 避免重复处理，提高效率

### 技术栈

| 类别 | 技术 |
|------|------|
| 后端语言 | Python 3.9+ |
| CLI 框架 | Typer + Rich |
| PDF 处理 | PyMuPDF, pdfplumber, MinerU |
| 数据处理 | Pandas, Pydantic |
| LLM 集成 | OpenAI SDK |
| 前端框架 | React 18 |
| 桌面框架 | Electron 28 |
| 构建工具 | Vite 5 |

### 项目结构

```
paperinsight/
├── core/          # 核心处理模块
├── parser/        # PDF 解析模块
├── cleaner/       # 文本清洗模块
├── llm/           # LLM 集成模块
├── models/        # 数据模型
├── ocr/           # OCR 模块
├── web/           # Web 服务模块
└── utils/         # 工具模块

desktop/           # 桌面应用
tests/             # 测试套件
scripts/           # 构建脚本
```

---

## 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/traditionalpc01-beep/paper-analysis-toolkit.git
cd paper-analysis-toolkit

# 安装依赖
pip install -r requirements.txt
pip install -e .
```

### 配置

```bash
# 运行配置向导
paperinsight config
```

### 使用

```bash
# 分析 PDF
paperinsight analyze ./pdfs

# 递归扫描 + JSON 输出
paperinsight analyze ./pdfs -r --json
```

---

## 核心流程

```
PDF 输入
    ↓
PDF 解析 (MinerU / PyMuPDF)
    ↓
文本清洗 (SectionFilter)
    ↓
数据提取 (LLM / Regex)
    ↓
数据验证 (Pydantic)
    ↓
影响因子补全 (Web 服务)
    ↓
报告生成 (Excel / JSON)
```

---

## 联系方式

- **项目地址**: https://github.com/traditionalpc01-beep/paper-analysis-toolkit
- **问题反馈**: https://github.com/traditionalpc01-beep/paper-analysis-toolkit/issues
- **版本**: 4.1.0
- **许可证**: MIT

---

## 文档更新

- **创建日期**: 2024-01-01
- **最后更新**: 2024-01-01
- **文档版本**: 1.0.0
