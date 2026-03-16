#!/bin/bash
# PaperInsight v3.0 启动脚本
# 用法: ./paperinsight.sh [命令] [参数]

# 激活虚拟环境（如果存在）
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# 运行 paperinsight
python -m paperinsight.cli "$@"
