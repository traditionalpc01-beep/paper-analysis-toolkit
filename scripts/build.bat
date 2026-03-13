@echo off
REM PaperInsight CLI 启动脚本 - Windows
REM 版本: 2.0.0

setlocal EnableDelayedExpansion

REM 获取脚本所在目录
set SCRIPT_DIR=%~dp0
set PROJECT_DIR=%SCRIPT_DIR%..

REM 切换到项目目录
cd /d "%PROJECT_DIR%"

REM 设置 Python 路径
set PYTHON_EXE=python

REM 检查 Python 是否存在
where %PYTHON_EXE% >nul 2>&1
if errorlevel 1 (
    REM 尝试 python3
    set PYTHON_EXE=python3
    where !PYTHON_EXE! >nul 2>&1
    if errorlevel 1 (
        echo.
        echo [错误] 未找到 Python 环境
        echo.
        echo 请安装 Python 3.8 或更高版本
        echo 下载地址: https://www.python.org/downloads/
        echo.
        pause
        exit /b 1
    )
)

REM 检查 Python 版本
%PYTHON_EXE% -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [错误] Python 版本过低
    echo.
    echo 请升级到 Python 3.8 或更高版本
    echo.
    pause
    exit /b 1
)

REM 检查是否安装了 paperinsight
%PYTHON_EXE% -c "import paperinsight" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [信息] PaperInsight 未安装,正在安装依赖...
    echo.
    
    REM 安装依赖
    %PYTHON_EXE% -m pip install -r requirements.txt -q
    if errorlevel 1 (
        echo [警告] 部分依赖安装失败,继续尝试运行...
    )
    
    REM 安装项目
    %PYTHON_EXE% -m pip install -e . -q
    if errorlevel 1 (
        echo [警告] 项目安装失败,使用开发模式运行...
    )
)

REM 运行 PaperInsight
%PYTHON_EXE% -m paperinsight.launcher %*

endlocal
