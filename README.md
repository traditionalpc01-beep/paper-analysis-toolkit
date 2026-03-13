# PDF论文分析工具包

## 📖 简介

这是一个用于自动分析PDF学术论文并提取关键信息的Python工具包。该工具能够从PDF文件中自动提取以下信息：

- 期刊名称和影响因子
- 论文标题和作者
- 器件结构
- 优化层级和策略
- EQE（外量子效率）
- CIE色度坐标
- 器件寿命
- 其他补充信息

最终生成一份按影响因子排序的Excel报告，便于快速了解论文质量和研究成果。

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 准备PDF文件

将待分析的PDF文件放入 `示例数据/pdfs/` 目录下。

### 3. 运行分析

```bash
python 脚本/analyze_papers.py
```

如果系统提示找不到 `python` 命令（Mac/Linux 常见），请改用：

```bash
python3 脚本/analyze_papers.py
```

常用参数示例：

```bash
# 递归扫描子目录 + 限制每篇最多读取前5页（加速）
# 同时导出 JSON/CSV + 缺失项报告（Markdown/Word）
python3 脚本/analyze_papers.py --recursive --max-pages 5 --export-json --export-csv --export-md --export-docx
```

### 4. 查看结果

分析完成后，结果将保存在 `输出结果/` 目录下，文件名格式为 `论文分析报告_时间戳.xlsx`。

## 📁 目录结构

```
论文分析工具包/
├── README.md                   # 使用说明文档
├── requirements.txt            # Python依赖包列表
├── 脚本/                       # 核心脚本目录
│   ├── analyze_papers.py      # 主分析脚本
├── 配置文件/                   # 配置文件目录
│   └── journal_impact_factors.json  # 期刊影响因子数据库
├── 示例数据/                   # 示例数据目录
│   └── pdfs/                  # PDF文件存放目录
├── 输出结果/                   # 分析结果输出目录
└── 使用文档/                   # 详细使用文档
    ├── 快速开始指南.md
    ├── 高级配置说明.md
    └── 常见问题解答.md
```

## ⚙️ 配置说明

### 修改PDF目录

推荐直接通过命令行参数传入：

```bash
python 脚本/analyze_papers.py \
  --pdf-dir /your/path/to/pdfs \
  --output-dir /your/path/to/output
```

### 扫描子目录 / 限制读取页数（加速）

```bash
# 递归扫描子目录中的 PDF
python 脚本/analyze_papers.py --pdf-dir /your/path/to/pdfs --recursive

# 每篇最多读取前 N 页（0 表示不限制）
python 脚本/analyze_papers.py --max-pages 5
```

### 导出 JSON / CSV（可选）

```bash
python 脚本/analyze_papers.py --export-json --export-csv
```

### 导出缺失项报告（Markdown / Word）

缺失项报告会逐篇列出哪些字段为空，并对关键指标（EQE/CIE/寿命）给出缺失原因：
- 文章类型原因（综述/理论/非器件性能类论文可能不适用）
- 更可能文章确实没有/未给出（未发现相关指标关键词）
- 文本提及但未提取（可能格式不同，需要补规则）

```bash
python3 脚本/analyze_papers.py --export-md --export-docx
```

输出文件名示例：
- `输出结果/论文缺失项报告_时间戳.md`
- `输出结果/论文缺失项报告_时间戳.docx`

### 添加期刊影响因子

优先编辑 `配置文件/journal_impact_factors.json`，脚本会在启动时自动加载：

```json
{
  "自定义期刊": {
    "Your Journal Name": {
      "impact_factor": 15.5,
      "category": "Materials Science"
    }
  }
}
```

如需只使用脚本内置期刊库，可添加 `--no-json` 参数。

## 📊 输出格式

生成的Excel文件包含以下列：

| 列名 | 说明 |
|------|------|
| File | PDF文件名 |
| URL | 文件路径 |
| 期刊名称 | 发表的期刊 |
| 影响因子 | 期刊IF值（2023-2024） |
| 作者 | 前3位作者 |
| 论文标题 | 论文标题 |
| 器件结构 | 器件各层材料 |
| 优化层级 | 优化层面 |
| 优化策略 | 具体优化方法 |
| EQE（外量子效率） | 器件EQE值 |
| 色度坐标 | CIE坐标 |
| 寿命 | T50或lifetime |
| 补充信息 | 波长、亮度等 |

## 🎯 适用场景

本工具特别适用于以下研究领域的论文分析：

- 量子点发光二极管（QLED）
- 钙钛矿太阳能电池
- 有机发光器件（OLED）
- 其他光电材料和器件

## ⚠️ 注意事项

1. **PDF质量**：确保PDF文件包含可提取的文本（非扫描版）
2. **期刊识别**：如期刊未被识别，将显示"未知期刊"，影响因子为0
3. **数据准确性**：自动提取的数据建议人工核对
4. **文件命名**：建议使用规范的文件命名（如：期刊 - 年份 - 作者 - 标题.pdf）

## 🔧 高级功能

### 批量处理

工具支持批量处理大量PDF文件，建议单次处理不超过100个文件。

### 自定义提取规则

可以在脚本中修改正则表达式模式，以适应不同的论文格式：

```python
# 修改EQE提取模式
patterns = [
    r'EQE[^0-9<≥>]*?([0-9]+\.?[0-9]*)\s*%',
    # 添加您的自定义模式
]
```

## 📞 技术支持

如有问题或建议，请联系开发团队。

## 📄 版本历史

- **v1.3** (2026-03-13)
  - 新增缺失项报告导出：Markdown（`--export-md`）与 Word（`--export-docx/--export-word`）
  - 缺失项报告会逐篇标注关键指标缺失原因（文章类型原因 vs 更可能未给出）
- **v1.2** (2026-03-13)
  - 支持递归扫描 PDF（`--recursive`），并兼容 `.PDF` 等大小写扩展名
  - 支持限制每篇论文读取页数（`--max-pages`），用于加速
  - 支持可选导出 JSON/CSV（`--export-json` / `--export-csv`）
  - 期刊识别改为优先基于“影响因子库”自动匹配（含常见缩写）
  - 标题/作者提取增加 PDF 元数据兜底与更稳的规则
- **v1.1** (2026-03-13)
  - 修复工作目录导致的路径错误
  - 支持 `--help` 和目录参数
  - 自动加载 JSON 期刊配置
  - 使用标准 `file://` URI 输出本地文件链接
- **v1.0** (2026-03-13)
  - 初始版本发布
  - 支持基本的PDF信息提取
  - 支持期刊识别和影响因子匹配
  - 支持按影响因子排序

---

**开发团队**: WorkBuddy AI Assistant  
**最后更新**: 2026-03-13
