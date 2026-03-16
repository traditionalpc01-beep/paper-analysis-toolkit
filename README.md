# PaperInsight CLI

智能科研论文分析工具 v3.0 - 自动提取 PDF 论文关键信息、补全影响因子并生成排序报告。

当前版本：`3.0.0`

---

## 重要：启动流程说明

**请严格按照以下顺序启动程序，不要跳过步骤：**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│   【推荐启动流程】必须按顺序执行                                          │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  第一步：环境检查                                                 │   │
│   │  ─────────────────────────────────────────────────────────────  │   │
│   │  命令: paperinsight check                                        │   │
│   │  检查: Python版本、核心依赖、网络连接、配置状态                    │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                              ↓                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  第二步：配置 API Key                                             │   │
│   │  ─────────────────────────────────────────────────────────────  │   │
│   │  命令: paperinsight config                                       │   │
│   │  配置: LLM提供商(DeepSeek/OpenAI/文心一言)、API Key               │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                              ↓                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  第三步：开始分析                                                 │   │
│   │  ─────────────────────────────────────────────────────────────  │   │
│   │  命令: paperinsight analyze ./pdfs                               │   │
│   │  流程: 环境自检 → 模式选择 → 任务输入 → 执行分析                   │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## v3.0 新特性

- **MinerU 解析器**：高性能 PDF 转 Markdown，支持表格、公式、图片提取
- **文本降噪**：自动过滤参考文献、致谢等噪声章节，聚焦核心内容
- **LLM 多厂商支持**：DeepSeek、OpenAI、百度文心一言
- **Pydantic 数据校验**：嵌套式 JSON Schema，确保数据结构正确
- **缓存优化**：基于 MD5 的智能缓存，避免重复解析

---

## 安装

```bash
# 克隆仓库
git clone https://github.com/traditionalpc01-beep/paper-analysis-toolkit.git
cd paper-analysis-toolkit

# 安装依赖
pip install -r requirements.txt
pip install -e .

# 可选：安装本地 OCR
pip install paddlepaddle paddleocr

# 可选：安装 OpenAI 客户端
pip install openai
```

### Windows 免安装可执行版

- 推送到 `main` 后，GitHub Actions 会自动构建 Windows 可执行包并上传为工作流产物。
- 推送 `v*` 标签后，会额外发布两个下载入口：
  - GitHub Release 附件：`PaperInsight-windows-x64-<版本>.zip`
  - GitHub Packages（NuGet）：`PaperInsight.Windows`
- 下载后解压，直接运行 `PaperInsight.exe check`、`PaperInsight.exe config`、`PaperInsight.exe analyze <PDF目录>` 即可。
- 示例发布命令：

```bash
git tag v3.0.0
git push origin main --tags
```

### 本地构建 Windows 可执行版

如果你在 Windows 机器上本地打包，可以直接运行：

```bash
python -m pip install ".[llm,build]"
python scripts/build_windows_exe.py
```

构建产物会输出到 `dist/`：

- `PaperInsight.exe`
- `PaperInsight-windows-x64-<版本>.zip`
- `PaperInsight-windows-x64-<版本>.zip.sha256`

## 桌面版应用

仓库现已新增 `React + Electron + Python` 的桌面版 MVP，代码位于 `desktop/`。

### 当前已实现

- 图形化界面：选择论文目录、输出目录、处理模式和运行选项
- 设置页：直接配置 API Key、LLM 提供商、MinerU 与运行引擎
- 双引擎设计：
  - `bundled`：面向普通用户的内置后端模式
  - `system_python`：面向高级用户的系统 Python 模式
- 后端桥接：`paperinsight.desktop_bridge` 用 JSON 消息驱动桌面端分析流程
- Windows 打包：GitHub Actions 可构建桌面安装包

### 本地启动桌面版

```bash
cd desktop
npm install
npm run dev
```

桌面端默认会优先尝试内置后端；开发环境下如果没有 `PaperInsightBackend.exe`，会自动回退到系统 Python：

```bash
python -m paperinsight.desktop_bridge config-get
```

### 本地构建桌面安装包

先构建 Windows 后端，再打桌面安装包：

```bash
python scripts/build_windows_exe.py --target desktop-backend
cd desktop
npm install
npm run dist:win
```

构建结果位于 `desktop/release/`。

---

## 启动方式

### 方式一：标准启动流程（推荐新用户）

**必须按以下顺序执行：**

```bash
# 第一步：环境检查
paperinsight check

# 第二步：配置 API Key
paperinsight config

# 第三步：开始分析
paperinsight analyze ./pdfs
```

### 方式二：快速启动（老用户）

已配置过的用户可以直接运行：

```bash
paperinsight analyze ./pdfs
```

程序会自动执行：
1. 环境自检（检测配置是否完整）
2. 模式选择（根据配置自动推荐）
3. 任务输入（支持交互式输入）

### 方式三：跳过检查启动（不推荐）

```bash
paperinsight analyze ./pdfs --skip-checks
```

⚠️ 不推荐新用户使用，可能导致配置缺失而运行失败。

---

## 命令详解

### 1. 环境检查命令

```bash
paperinsight check
```

**检查项目：**
- Python 版本（需 3.9+）
- 核心依赖（typer, rich, PyMuPDF, openpyxl, pydantic）
- 网络连接
- 配置状态

**这是启动流程的第一步，不要跳过！**

### 2. 配置命令

```bash
paperinsight config
```

**配置向导支持：**
- **DeepSeek**（推荐，性价比高）
- **OpenAI GPT-4**
- **百度文心一言**
- **MinerU**（本地/云端）
- **PaddleX OCR**

**配置文件保存在：** `~/.paperinsight/config.yaml`（仅本地存储，不会上传）

**这是启动流程的第二步，不要跳过！**

### 3. 分析命令

```bash
# 交互式启动
paperinsight analyze

# 指定目录
paperinsight analyze ./pdfs

# 递归扫描
paperinsight analyze ./pdfs -r

# 指定模式和输出
paperinsight analyze ./pdfs --mode api -o ./reports

# 完整参数
paperinsight analyze ./pdfs -r -o ./reports --mode api --max-pages 10 --json --rename-pdfs
```

**参数说明：**
| 参数 | 说明 |
|------|------|
| `--mode` | 运行模式: auto(自动), api(智能API), regex(基础正则) |
| `--output, -o` | 输出目录 |
| `--recursive, -r` | 递归扫描子目录 |
| `--max-pages` | 每篇论文最大读取页数 |
| `--json` | 同时导出 JSON 报告 |
| `--rename-pdfs` | 处理后重命名 PDF |
| `--no-cache` | 禁用缓存 |
| `--skip-checks` | 跳过启动检查（不推荐） |

**这是启动流程的第三步！**

### 4. 其他命令

```bash
# 完整诊断
paperinsight doctor

# 查看版本
paperinsight version

# 缓存管理
paperinsight cache-info
paperinsight clear-cache

# 查看帮助
paperinsight --help
paperinsight analyze --help
```

---

## 运行模式详解

### 智能 API 模式 (`--mode api`)

- 调用 LLM 进行语义提取
- 调用 OCR API 处理扫描版 PDF
- 自动补全影响因子
- 适合追求精度的批处理场景
- **需要配置 API Key**

### 基础正则模式 (`--mode regex`)

- 纯本地处理，无需 API
- 速度极快，免费
- 对扫描版和复杂版式支持有限
- 适合快速试跑
- **无需配置 API Key**

### 自动模式 (`--mode auto`，默认)

- 根据配置自动选择最佳模式
- 有 API 配置时使用智能模式
- 无 API 配置时使用基础模式

---

## 程序内部执行流程

当你运行 `paperinsight analyze` 时，程序会按以下顺序执行：

```
┌─────────────────────────────────────────────────────────────┐
│  【第一步】环境自检                                          │
│  ─────────────────────────────────────────────────────────  │
│  1. 检查 Python 版本 >= 3.9                                 │
│  2. 检查核心依赖完整性                                       │
│  3. 检查配置文件完整性                                       │
│  4. 缺失配置时提示进入配置向导                               │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  【第二步】模式选择                                          │
│  ─────────────────────────────────────────────────────────  │
│  1. 显示可选模式（API模式 / 正则模式）                       │
│  2. 根据配置自动推荐                                         │
│  3. 用户确认选择                                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  【第三步】任务输入                                          │
│  ─────────────────────────────────────────────────────────  │
│  1. 获取 PDF 目录路径                                        │
│  2. 检查目录是否存在、是否包含 PDF                           │
│  3. 设置输出目录                                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  【第四步】执行分析                                          │
│  ─────────────────────────────────────────────────────────  │
│  1. 显示运行配置摘要                                         │
│  2. 用户确认执行                                             │
│  3. 执行分析管线                                             │
│  4. 生成报告                                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 输出内容

默认生成 `输出结果/` 文件夹：

```
输出结果/
├── Paper_Analysis_Report.xlsx  # Excel 报告（按 IF 降序）
├── Paper_Analysis_Report.json  # JSON 数据（--json 时）
├── error_log.txt               # 错误日志
└── renamed_pdfs/               # 重命名的 PDF（--rename-pdfs 时）
```

**Excel 字段说明：**

| 字段 | 说明 |
|------|------|
| 期刊名称 | 从首页或页眉提取 |
| 影响因子 | PDF 原文或 Web 搜索补全 |
| 论文标题 | 首页最大字号文本 |
| 作者 | 论文署名 |
| 器件结构 | 层级堆叠（如 ITO/HTL/EML...） |
| EQE / CIE / 寿命 | 多器件数据用换行分隔 |
| 数据溯源 | 原文出处句子 |
| 优化层级 | 器件优化级别 |
| 优化策略 | 总结（约100字） |

---

## 配置文件示例

`~/.paperinsight/config.yaml`:

```yaml
# LLM 配置
llm:
  enabled: true
  provider: "deepseek"        # openai / deepseek / wenxin
  api_key: "sk-xxx"           # 本地加密存储
  model: "deepseek-chat"
  base_url: ""                # 可选：自定义 API 端点
  timeout: 120

# MinerU 配置
mineru:
  enabled: true
  mode: "cli"                 # cli / api
  token: ""                   # API 模式需要

# PaddleX OCR 配置
paddlex:
  enabled: false
  token: ""
  model: "PaddleOCR-VL-1.5"

# Web 搜索
web_search:
  enabled: true
  timeout: 30

# 缓存
cache:
  enabled: true
  directory: ".cache"

# 输出
output:
  format: ["excel"]
  sort_by_if: true
  generate_error_log: true
  rename_pdfs: false
  rename_template: "[{year}_{impact_factor}_{journal}]_{title}.pdf"

# PDF 处理
pdf:
  max_pages: 0
  text_ratio_threshold: 0.1
```

---

## 安全说明

- **所有 API Key 仅存储在本地**
- 配置文件使用 XOR + Base64 加密
- 不会上传到远程服务器
- 建议将 `~/.paperinsight/` 添加到 `.gitignore`

---

## 常见问题

### Q: 首次运行应该怎么做？

**A: 严格按照以下顺序：**
```bash
paperinsight check     # 第一步
paperinsight config    # 第二步
paperinsight analyze   # 第三步
```

### Q: 程序启动失败怎么办？

**A: 按以下步骤排查：**
1. 运行 `paperinsight check` 检查环境
2. 运行 `paperinsight doctor` 完整诊断
3. 根据提示安装缺失依赖或配置 API Key

### Q: 不想配置 API Key 可以用吗？

**A: 可以，但功能受限：**
- 使用基础正则模式：`paperinsight analyze ./pdfs --mode regex`
- 精度较低，无法处理扫描版 PDF
- 无法使用 LLM 语义提取

### Q: 为什么强调按顺序启动？

**A: 因为程序依赖正确的环境配置：**
- 第一步确保运行环境正确
- 第二步确保 API 配置完整
- 第三步才能正常执行分析
- 跳过步骤可能导致运行失败

---

## 文档

- [快速开始指南](./使用文档/快速开始指南.md)
- [使用示例](./使用文档/使用示例.md)
- [高级配置说明](./使用文档/高级配置说明.md)
- [常见问题解答](./使用文档/常见问题解答.md)

---

## 注意事项

- API 模式依赖网络和有效凭证
- 扫描版 PDF 建议配置 OCR 能力
- 自动提取结果建议人工抽样复核
- Web 搜索补全的影响因子可能受网站可用性影响

---

## 许可证

MIT License
