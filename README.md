# PaperInsight CLI

智能科研论文分析工具 - 自动提取 PDF 论文关键信息并生成报告

版本: 2.0.0

## 功能特点

- 自动提取期刊名称、标题、作者等信息
- 支持百度 OCR API 进行扫描版 PDF 识别
- 集成 LLM 进行语义提取(支持 OpenAI、DeepSeek)
- 自动补全期刊影响因子(支持 Web 搜索)
- 智能缓存系统,支持断点续传
- 生成按影响因子排序的 Excel 报告
- 支持多器件参数提取和数据溯源

## 快速开始

### 1. 安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/paperinsight.git
cd paperinsight

# 安装核心依赖
pip install -r requirements.txt

# 可选: 安装 OCR 支持
pip install paddlepaddle paddleocr

# 可选: 安装 LLM 支持
pip install openai

# 安装项目
pip install -e .
```

### 2. 基本使用

```bash
# 分析 PDF 目录
paperinsight analyze ./pdfs

# 递归扫描子目录
paperinsight analyze ./pdfs --recursive

# 指定输出目录
paperinsight analyze ./pdfs --output ./reports

# 使用智能 API 模式
paperinsight analyze ./pdfs --mode api

# 同时导出 JSON 报告
paperinsight analyze ./pdfs --json
```

### 3. 配置 API Key

首次使用智能 API 模式时,会自动启动配置向导:

```bash
paperinsight analyze ./pdfs --mode api
```

或手动配置:

```bash
paperinsight config
```

配置文件位于 `~/.paperinsight/config.yaml`

## 运行模式

### 基础正则模式 (默认)

- 使用正则表达式提取信息
- 无需 API Key
- 速度快,准确度适中

### 智能 API 模式

- 调用百度 OCR API 进行高精度识别
- 调用 LLM 进行语义提取
- 需要配置 API Key
- 准确度高,消耗 API 额度

```bash
paperinsight analyze ./pdfs --mode api
```

## 提取字段

| 字段 | 说明 |
|------|------|
| 期刊名称 | 从首页或页眉页脚提取 |
| 影响因子 | 优先匹配 PDF 原文,其次通过 Web 查询 |
| 论文标题 | 识别第一页最大字号文本 |
| 作者 | 最多列出前 3 位 |
| 器件结构 | 识别层级堆叠结构 |
| EQE | 外量子效率(支持多器件) |
| CIE | 色度坐标(支持多器件) |
| 寿命 | T50/LT50(支持多器件) |
| 数据溯源 | 附带原文出处句子 |
| 优化层级和策略 | 总结优化方法(约 100 字) |

## 命令参考

### analyze

分析 PDF 论文

```bash
paperinsight analyze PDF_DIR [OPTIONS]

选项:
  --output, -o PATH    输出目录
  --recursive, -r      递归扫描子目录
  --max-pages INT      最大读取页数(0 表示不限制)
  --mode, -m TEXT      运行模式: auto, api, regex
  --no-cache           禁用缓存
  --json               同时导出 JSON 报告
```

### config

配置 API Key

```bash
paperinsight config
```

### cache-info

显示缓存信息

```bash
paperinsight cache-info
```

### clear-cache

清除所有缓存

```bash
paperinsight clear-cache
```

### version

显示版本信息

```bash
paperinsight version
```

## 环境检查

### 快速检查

```bash
# 快速检查必要条件
paperinsight check

# 完整环境诊断
paperinsight doctor
```

### 启动时自动检查

启动脚本会自动检测运行环境:

1. **检查 Python 环境**: 确保版本 >= 3.8
2. **检查网络连接**: 判断是否可以使用在线 API
3. **检查依赖完整性**: 确保核心依赖已安装
4. **检查本地 OCR**: 判断是否可以处理扫描版 PDF

### 离线模式

当检测到无法联网时:

1. 如果本地 PaddleOCR 已安装 → 使用本地 OCR 处理
2. 如果本地 OCR 不可用 → 仅处理包含文本层的 PDF

### Windows 启动脚本

```batch
# 双击运行
scripts\build.bat

# 或命令行运行
scripts\build.bat analyze ./pdfs
```

### Linux/macOS 启动脚本

```bash
# 添加执行权限
chmod +x scripts/paperinsight.sh

# 运行
./scripts/paperinsight.sh analyze ./pdfs
```

## 缓存系统

工具使用智能缓存系统提高效率:

- `[MD5]_data.json`: 完整提取结果
- `[MD5]_ocr.txt`: OCR 文本(可复用)

重复运行时,会自动跳过已处理的文件。

## 项目结构

```
paperinsight/
├── cli.py                 # CLI 入口
├── core/
│   ├── cache.py          # 缓存管理
│   ├── extractor.py      # 数据提取器
│   ├── pipeline.py       # 处理管线
│   └── reporter.py       # 报告生成器
├── ocr/
│   ├── baidu_api.py      # 百度 OCR API
│   ├── local.py          # 本地 PaddleOCR
│   └── base.py           # OCR 基类
├── llm/
│   ├── openai_client.py  # OpenAI 客户端
│   ├── deepseek_client.py # DeepSeek 客户端
│   ├── prompt_templates.py # Prompt 模板
│   └── base.py           # LLM 基类
├── web/
│   └── impact_factor_search.py # 影响因子搜索
└── utils/
    ├── pdf_utils.py      # PDF 处理工具
    ├── hash_utils.py     # 哈希工具
    └── logger.py         # 日志系统
```

## 配置说明

配置文件示例 (`~/.paperinsight/config.yaml`):

```yaml
# 百度 OCR API 配置
baidu_ocr:
  enabled: true
  api_key: "your-api-key"
  secret_key: "your-secret-key"

# LLM 配置
llm:
  enabled: true
  provider: "openai"
  api_key: "your-api-key"
  model: "gpt-4o"

# Web 搜索配置
web_search:
  enabled: true
```

## API Key 获取

### 百度 OCR API

1. 访问 [百度智能云](https://console.bce.baidu.com/ai/#/ai/ocr/overview/index)
2. 创建应用,获取 API Key 和 Secret Key
3. 免费额度: 通用文字识别 500 次/天

### OpenAI API

1. 访问 [OpenAI Platform](https://platform.openai.com/api-keys)
2. 创建 API Key
3. 按使用量计费

### DeepSeek API

1. 访问 [DeepSeek Platform](https://platform.deepseek.com/api_keys)
2. 创建 API Key
3. 性价比高,中文友好

## 注意事项

1. **PDF 质量**: 确保文件可读,扫描版需使用 OCR
2. **API 额度**: 注意百度 OCR 和 LLM 的使用额度
3. **数据准确性**: 自动提取的数据建议人工核对
4. **网络要求**: Web 搜索和 API 模式需要网络连接

## 版本历史

### v2.0.0 (2026-03-13)

- 完全重构为模块化架构
- 新增百度 OCR API 支持
- 新增 LLM 语义提取
- 新增智能缓存系统
- 新增 Web 搜索补全影响因子
- 新增数据溯源字段
- 重构 CLI 框架(Typer)
- 改进异常隔离和错误日志

### v1.4 (2026-03-13)

- 新增缺失项报告导出
- 支持递归扫描 PDF
- 支持本地 PaddleOCR

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request!

---

**开发团队**: WorkBuddy AI Assistant  
**最后更新**: 2026-03-13
