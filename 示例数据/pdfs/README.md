# 示例 PDF 目录说明

这个目录用于放待分析的 PDF 文件。本文只保留当前仓库里可以直接核查的使用方式。

## 使用方式

1. 把待分析的 `.pdf` 文件放入当前目录。
2. 在项目根目录运行：

```bash
paperinsight analyze ./示例数据/pdfs
```

3. 默认输出会写到：

```text
./示例数据/pdfs/输出结果/
```

## 当前支持的 PDF 处理思路

- 文本型 PDF：可直接走基础提取或 MinerU 解析。
- 扫描型 PDF：建议配置 MinerU、PaddleX 或本地 OCR。
- 混合型 PDF：由解析器与回退逻辑按当前配置处理。

## 常见命令

```bash
# 先做环境检查
paperinsight check

# 运行配置向导
paperinsight config

# 开始分析
paperinsight analyze ./示例数据/pdfs

# 递归处理子目录
paperinsight analyze ./示例数据/pdfs --recursive
```

## 输出文件

当前实现默认生成：

- `论文分析报告_<时间戳>.xlsx`
- `论文分析报告_<时间戳>.json`（仅在启用 JSON 导出时）
- `error_log.txt`（仅在有错误时）

## 缓存说明

默认缓存目录是项目根目录下的 `.cache/`，常见文件名包括：

- `<md5>_data.json`
- `<md5>_markdown.md`
- 兼容旧版 `<md5>_ocr.md`

## 可核查来源

### 仓库内

- `paperinsight/cli.py`
- `paperinsight/core/pipeline.py`
- `paperinsight/core/reporter.py`
- `paperinsight/core/cache.py`
- `README.md`

### 外部官方文档

- MinerU 官方文档：<https://mineru.net/apiManage/docs>
