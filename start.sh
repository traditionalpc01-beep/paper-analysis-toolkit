#!/bin/bash
# ========================================
# PDF论文分析工具 - 快速启动脚本
# ========================================

echo ""
echo "========================================"
echo "   PDF论文分析工具 v1.1"
echo "   WorkBuddy AI Assistant"
echo "========================================"
echo ""

# 切换到脚本目录
cd "$(dirname "$0")"

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未检测到Python"
    echo "请先安装Python 3.8或更高版本"
    exit 1
fi

# 显示菜单
while true; do
    echo ""
    echo "请选择操作:"
    echo ""
    echo " [1] 首次使用 - 安装依赖包"
    echo " [2] 运行分析 - 分析PDF论文"
    echo " [3] 查看结果 - 打开输出目录"
    echo " [4] 查看帮助 - 打开使用文档"
    echo " [5] 退出"
    echo ""
    
    read -p "请输入选项 (1-5): " choice
    
    case $choice in
        1)
            echo ""
            echo "[1/3] 检查依赖包..."
            if python3 -c "import pdfplumber" &> /dev/null; then
                echo "依赖包已安装"
                continue
            fi
            
            echo ""
            echo "[2/3] 正在安装依赖包..."
            pip3 install -r requirements.txt
            
            if [ $? -eq 0 ]; then
                echo ""
                echo "[3/3] 安装完成！"
            else
                echo "[错误] 安装失败，请检查网络连接"
            fi
            ;;
        2)
            echo ""
            echo "[1/2] 检查PDF文件..."
            
            pdf_count=$(find 示例数据/pdfs -name "*.pdf" -type f | wc -l)
            
            if [ "$pdf_count" -eq 0 ]; then
                echo "[错误] 未找到PDF文件！"
                echo "请将PDF文件放入: 示例数据/pdfs/"
                continue
            fi
            
            echo "找到 $pdf_count 个PDF文件"
            echo ""
            echo "[2/2] 开始分析..."
            echo ""
            python3 脚本/analyze_papers.py
            
            echo ""
            echo "分析完成！"
            ;;
        3)
            echo ""
            echo "打开输出目录..."
            
            if [[ "$OSTYPE" == "darwin"* ]]; then
                open 输出结果/
            elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
                xdg-open 输出结果/
            else
                echo "输出目录: $(pwd)/输出结果/"
            fi
            ;;
        4)
            echo ""
            echo "打开使用文档..."
            
            if [[ "$OSTYPE" == "darwin"* ]]; then
                open README.md
            else
                cat README.md | less
            fi
            ;;
        5)
            echo ""
            echo "感谢使用！"
            exit 0
            ;;
        *)
            echo ""
            echo "[错误] 无效选项，请重新选择"
            ;;
    esac
done
