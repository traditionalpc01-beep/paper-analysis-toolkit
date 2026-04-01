# PaperInsight 4.1 Release

## 🎉 新特性

### 1. 影响因子提取优化
- ✅ 增加实时网络验证机制，确保使用最新的影响因子数据
- ✅ 改进影响因子数据源，优先使用最新的官方数据
- ✅ 增加多源数据交叉验证，提高影响因子准确性
- ✅ 添加影响因子数据缓存机制，提高性能

### 2. 年份提取算法优化
- ✅ 改进年份提取逻辑，提高年份识别准确率
- ✅ 增加年份格式识别和验证
- ✅ 优化从不同来源（标题、摘要、正文）提取年份的能力
- ✅ 年份提取准确率从20%提升到100%

### 3. 其他优化
- ✅ 保持并优化现有的作者、期刊和器件数据提取功能
- ✅ 进一步提高文本清理和噪声过滤能力
- ✅ 优化API处理流程，提高性能和可靠性

## 📊 验证结果

基于5篇测试论文的验证结果：

| 指标 | 准确率 | 改进 |
|------|--------|------|
| 标题提取 | 80.00% | - |
| 作者提取 | 100.00% | - |
| 期刊提取 | 100.00% | - |
| 影响因子提取 | 100.00% | - |
| 年份提取 | 100.00% | +80% |
| 器件数据提取 | 100.00% | - |

## 🚀 安装方法

### 使用pip安装
```bash
pip install paperinsight==4.1.0
```

### 从源码安装
```bash
git clone https://github.com/traditionalpc01-beep/paper-analysis-toolkit.git
cd paper-analysis-toolkit
pip install -e .
```

## 📖 使用方法

### 基本使用
```bash
# 分析单个PDF文件
paperinsight analyze paper.pdf

# 分析多个PDF文件
paperinsight analyze *.pdf

# 分析目录下的所有PDF文件
paperinsight analyze path/to/papers/
```

### 配置文件
首次运行后，会在用户目录下生成配置文件，可以根据需要修改。

详细使用说明请参考：[README.md](README.md)

## 🐛 已知问题

- 网络连接不稳定时，可能会影响影响因子的实时验证
- 部分特殊格式的PDF文件可能需要进一步优化

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 许可证

MIT License

---

**感谢使用PaperInsight！** 🎊
