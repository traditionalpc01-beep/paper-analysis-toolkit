# PDF文件存放目录

## 使用说明

1. 将待分析的PDF论文文件放入此目录
2. PDF文件扩展名支持 `.pdf` / `.PDF` 等大小写
3. 运行分析脚本后，结果将保存在 `../输出结果/` 目录

## 文件命名建议

推荐使用以下命名格式，便于识别：

```
期刊名 - 年份 - 第一作者 - 论文标题.pdf
```

示例：
```
Advanced Materials - 2025 - Zhang - High Performance QLEDs.pdf
Nature Communications - 2024 - Li - Efficient Perovskite Solar Cells.pdf
```

## 支持的PDF类型

- ✅ 文本型PDF（可提取文字）
- ❌ 扫描型PDF（图片格式，需先OCR处理）

## 注意事项

- 单次建议处理不超过100个PDF文件
- 如PDF文件较大（>50MB），处理时间会较长
- 损坏的PDF文件会被自动跳过

---

**准备就绪后，请运行：**
```bash
cd ../../脚本
python analyze_papers.py
```

如果系统提示找不到 `python` 命令，请改用：
```bash
python3 analyze_papers.py
```
