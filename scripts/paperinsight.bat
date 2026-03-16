@echo off
REM PaperInsight v3.0 启动脚本 (Windows)
REM 用法: paperinsight.bat [命令] [参数]

REM 激活虚拟环境（如果存在）
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM 运行 paperinsight
python -m paperinsight.cli %*
