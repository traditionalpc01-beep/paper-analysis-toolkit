#!/bin/bash
# Linux/Mac Shell脚本 - 运行PDF论文分析工具

echo "===================================="
echo "PDF论文分析工具 - 启动脚本"
echo "===================================="
echo ""

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "错误: 未检测到Python3，请先安装Python 3.8或更高版本"
    exit 1
fi

# 显示Python版本
echo "Python版本:"
python3 --version
echo ""

# 检查依赖包
echo "检查依赖包..."
if ! python3 -c "import pdfplumber" &> /dev/null; then
    echo "正在安装依赖包..."
    pip3 install -r ../requirements.txt
fi

echo ""
echo "开始分析..."
echo ""

# 运行主脚本
cd ..
python3 脚本/analyze_papers.py

echo ""
echo "===================================="
echo "分析完成！"
echo "===================================="
echo ""
echo "结果已保存在: 输出结果/"
echo ""

# 如果是Mac，自动打开结果目录
if [[ "$OSTYPE" == "darwin"* ]]; then
    read -p "是否打开输出目录? (y/n): " open_result
    if [ "$open_result" = "y" ]; then
        open 输出结果/
    fi
fi
