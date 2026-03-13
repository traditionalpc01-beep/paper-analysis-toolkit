@echo off
REM Windows批处理脚本 - 运行PDF论文分析工具

echo ====================================
echo PDF论文分析工具 - 启动脚本
echo ====================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未检测到Python，请先安装Python 3.8或更高版本
    pause
    exit /b
)

REM 检查依赖包
echo 检查依赖包...
pip show pdfplumber >nul 2>&1
if errorlevel 1 (
    echo 正在安装依赖包...
    pip install -r ..\requirements.txt
)

echo.
echo 开始分析...
echo.

REM 运行主脚本
cd ..
python 脚本\analyze_papers.py

echo.
echo ====================================
echo 分析完成！
echo ====================================
echo.
echo 结果已保存在: 输出结果\
echo.
pause
