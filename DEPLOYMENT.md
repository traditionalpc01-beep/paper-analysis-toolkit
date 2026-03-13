# 工具包部署说明

## 打包和分发

### 方法一：直接压缩（推荐）

1. **压缩整个文件夹**
   ```bash
   # Linux/Mac
   cd /Users/locybe/论文处理
   zip -r 论文分析工具包.zip 论文分析工具包/
   
   # Windows (使用右键菜单)
   右键点击"论文分析工具包"文件夹 -> 发送到 -> 压缩(zipped)文件夹
   ```

2. **分发压缩包**
   - 通过邮件发送
   - 上传到云盘分享
   - 通过U盘拷贝

### 方法二：创建自包含包

1. **创建独立环境**
   ```bash
   # 创建虚拟环境
   python -m venv venv
   
   # 激活环境
   source venv/bin/activate  # Linux/Mac
   # 或
   venv\Scripts\activate     # Windows
   
   # 安装依赖
   pip install -r requirements.txt
   ```

2. **打包整个环境**
   ```bash
   # 将venv文件夹也打包进去
   zip -r 论文分析工具包_完整版.zip 论文分析工具包/ venv/
   ```

---

## 安装部署

### 接收方安装步骤

1. **解压文件**
   ```bash
   # 解压到任意目录
   unzip 论文分析工具包.zip
   cd 论文分析工具包
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **验证安装**
   ```bash
   python 脚本/analyze_papers.py
   # 应显示"找到 0 个PDF文件"（正常，因为还没放PDF）
   ```

4. **开始使用**
   - 将PDF文件放入 `示例数据/pdfs/`
   - 运行分析脚本

---

## 自定义部署

### 添加自定义期刊

1. **编辑配置文件**
   ```bash
   # 编辑 配置文件/journal_impact_factors.json
   # 添加您的期刊和影响因子
   ```

2. **直接运行脚本**
   - 主脚本会自动读取 `配置文件/journal_impact_factors.json`
   - 无需额外修改代码

### 修改默认路径

推荐直接通过命令行参数指定：

```bash
python 脚本/analyze_papers.py \
  --pdf-dir /your/custom/path/to/pdfs \
  --output-dir /your/custom/output/path
```

---

## 批量部署

### 为团队部署

1. **创建共享版本**
   - 将PDF目录改为共享网络路径
   - 将输出目录改为共享存储

2. **配置文件示例**
   ```python
   # config.py
   PDF_DIR = Path("//server/shared/papers")
   OUTPUT_DIR = Path("//server/shared/results")
   ```

3. **分发配置**
   - 将修改后的工具包分发给团队成员
   - 每个人使用相同的配置

---

## 容器化部署（高级）

### 使用Docker

1. **创建Dockerfile**
   ```dockerfile
   FROM python:3.10-slim
   
   WORKDIR /app
   
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   
   COPY . .
   
   CMD ["python", "脚本/analyze_papers.py"]
   ```

2. **构建镜像**
   ```bash
   docker build -t paper-analyzer .
   ```

3. **运行容器**
   ```bash
   docker run -v $(pwd)/示例数据/pdfs:/app/示例数据/pdfs \
              -v $(pwd)/输出结果:/app/输出结果 \
              paper-analyzer
   ```

---

## 云端部署

### GitHub/Gitee

1. **创建仓库**
   ```bash
   git init
   git add .
   git commit -m "Initial commit: PDF论文分析工具 v1.0"
   git remote add origin https://github.com/username/paper-analyzer.git
   git push -u origin main
   ```

2. **添加README和文档**
   - 已包含完整的README.md
   - 使用文档齐全

3. **添加.gitignore**
   ```
   # .gitignore
   __pycache__/
   *.pyc
   venv/
   示例数据/pdfs/*.pdf
   输出结果/*.xlsx
   ```

---

## 版本控制

### 版本号规则

- **主版本号 (Major)**: 重大功能变更
- **次版本号 (Minor)**: 新增功能
- **修订号 (Patch)**: Bug修复

示例：
- v1.0.0 - 首次发布
- v1.1.0 - 新增JSON导出
- v1.1.1 - 修复EQE提取bug

### 发布流程

1. 更新VERSION.md
2. 测试所有功能
3. 更新文档
4. 创建Git标签
   ```bash
   git tag -a v1.1.0 -m "Release v1.1.0"
   git push origin v1.1.0
   ```
5. 打包分发
   ```bash
   zip -r 论文分析工具包_v1.1.0.zip 论文分析工具包/
   ```

---

## 维护和更新

### 定期更新

1. **更新影响因子**
   - 每年更新JCR数据
   - 修改 `JOURNAL_IMPACT_FACTORS` 字典

2. **更新依赖包**
   ```bash
   pip install --upgrade pdfplumber openpyxl
   pip freeze > requirements.txt
   ```

3. **备份和归档**
   ```bash
   # 备份重要结果
   cp -r 输出结果/ 备份/输出结果_$(date +%Y%m%d)/
   ```

---

## 技术支持

### 问题排查

1. **查看日志**
   ```bash
   # 在脚本中添加日志记录
   import logging
   logging.basicConfig(filename='analyzer.log', level=logging.INFO)
   ```

2. **调试模式**
   ```python
   # 在analyze_papers.py中启用
   DEBUG = True
   ```

### 获取帮助

1. 查看FAQ文档
2. 查看高级配置说明
3. 联系开发团队

---

**最后更新**: 2026-03-13
