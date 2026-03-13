@echo off
REM ========================================
REM PDF论文分析工具 - 快速启动脚本
REM ========================================

echo.
echo ========================================
echo    PDF论文分析工具 v1.1
echo    WorkBuddy AI Assistant
echo ========================================
echo.

REM 切换到脚本目录
cd /d "%~dp0"

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Python
    echo 请先安装Python 3.8或更高版本
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b
)

REM 显示菜单
:menu
echo.
echo 请选择操作:
echo.
echo  [1] 首次使用 - 安装依赖包
echo  [2] 运行分析 - 分析PDF论文
echo  [3] 查看结果 - 打开输出目录
echo  [4] 查看帮助 - 打开使用文档
echo  [5] 退出
echo.

set /p choice="请输入选项 (1-5): "

if "%choice%"=="1" goto install
if "%choice%"=="2" goto run
if "%choice%"=="3" goto open
if "%choice%"=="4" goto help
if "%choice%"=="5" goto end

echo.
echo [错误] 无效选项，请重新选择
goto menu

:install
echo.
echo [1/3] 检查依赖包...
pip show pdfplumber >nul 2>&1
if not errorlevel 1 (
    echo 依赖包已安装
    goto menu
)

echo.
echo [2/3] 正在安装依赖包...
pip install -r requirements.txt
if errorlevel 1 (
    echo [错误] 安装失败，请检查网络连接
    pause
    goto menu
)

echo.
echo [3/3] 安装完成！
pause
goto menu

:run
echo.
echo [1/2] 检查PDF文件...
if not exist "示例数据\pdfs\*.pdf" (
    echo [错误] 未找到PDF文件！
    echo 请将PDF文件放入: 示例数据\pdfs\
    pause
    goto menu
)

echo.
echo [2/2] 开始分析...
echo.
python 脚本\analyze_papers.py

echo.
echo 分析完成！
pause
goto menu

:open
echo.
echo 打开输出目录...
start "" "输出结果"
goto menu

:help
echo.
echo 打开使用文档...
start "" "README.md"
goto menu

:end
echo.
echo 感谢使用！
timeout /t 2 >nul
exit
