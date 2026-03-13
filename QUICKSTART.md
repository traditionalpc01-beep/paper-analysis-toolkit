# 快速参考卡片

## 🚀 三步快速开始

```bash
# 1️⃣ 安装依赖
pip install -r requirements.txt

# 2️⃣ 放入PDF
cp your_papers.pdf 示例数据/pdfs/

# 3️⃣ 运行分析
python 脚本/analyze_papers.py
```

## 📁 重要目录

| 目录 | 说明 |
|------|------|
| `示例数据/pdfs/` | 放入PDF文件 |
| `输出结果/` | 查看分析结果 |
| `配置文件/` | 修改配置 |

## 🔧 常用命令

```bash
# 查看帮助
python 脚本/analyze_papers.py --help

# 指定自定义目录
python 脚本/analyze_papers.py --pdf-dir /path/to/pdfs --output-dir /path/to/output

# 测试安装
python -c "import pdfplumber, openpyxl; print('OK')"

# 更新依赖
pip install --upgrade -r requirements.txt
```

## 📊 输出字段

| 字段 | 说明 |
|------|------|
| 期刊名称 | 发表期刊 |
| 影响因子 | 期刊IF |
| EQE | 外量子效率 |
| 寿命 | T50寿命 |
| CIE | 色度坐标 |

## ⚠️ 常见问题

**Q: 找不到PDF？**  
A: 确认文件在 `示例数据/pdfs/` 且扩展名是 `.pdf`

**Q: 期刊显示"未知"？**  
A: 在 `配置文件/journal_impact_factors.json` 中添加期刊，脚本会自动加载

**Q: EQE未提取？**  
A: 可能是非器件类文章，或格式特殊

## 📞 获取帮助

- 📖 查看 `README.md`
- 📚 查看 `使用文档/` 目录
- 🔍 搜索关键词

## 📌 记住

1. PDF要放对位置 ✅
2. 先装依赖包 ✅
3. 结果在输出目录 ✅

---

**版本**: v1.1 | **更新**: 2026-03-13
