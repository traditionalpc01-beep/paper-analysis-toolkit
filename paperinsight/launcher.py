"""
启动器模块
功能: 检测环境并选择最佳运行方式
"""

import sys
from typing import Optional


def print_banner():
    """打印启动横幅"""
    print("=" * 60)
    print("  PaperInsight CLI v2.0.0")
    print("  智能科研论文分析工具")
    print("=" * 60)
    print()


def print_error(message: str, details: Optional[str] = None):
    """打印错误信息"""
    print(f"\n[错误] {message}")
    if details:
        print(f"  详情: {details}")
    print()


def print_warning(message: str, details: Optional[str] = None):
    """打印警告信息"""
    print(f"\n[警告] {message}")
    if details:
        print(f"  详情: {details}")


def print_info(message: str):
    """打印信息"""
    print(f"[信息] {message}")


def check_network() -> bool:
    """检查网络连接"""
    try:
        import requests
        # 尝试访问百度
        response = requests.head("https://www.baidu.com", timeout=5)
        return True
    except Exception:
        return False


def check_python_env() -> bool:
    """检查 Python 环境"""
    return sys.version_info >= (3, 8)


def check_paddleocr() -> bool:
    """检查 PaddleOCR 是否可用"""
    try:
        import paddleocr
        import paddle
        return True
    except ImportError:
        return False


def check_dependencies() -> tuple[bool, list[str]]:
    """
    检查核心依赖
    
    Returns:
        (是否完整, 缺失的依赖列表)
    """
    missing = []
    
    required = [
        ("typer", "typer"),
        ("rich", "rich"),
        ("fitz", "PyMuPDF"),
        ("openpyxl", "openpyxl"),
        ("yaml", "pyyaml"),
        ("requests", "requests"),
    ]
    
    for module, package in required:
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    
    return len(missing) == 0, missing


def run_with_python(args: list[str]) -> int:
    """
    使用 Python 运行
    
    Args:
        args: 命令行参数
    
    Returns:
        退出码
    """
    from paperinsight.cli import app
    
    try:
        app(args)
        return 0
    except SystemExit as e:
        return e.code or 0
    except Exception as e:
        print_error("运行出错", str(e))
        return 1


def diagnose_and_run(args: list[str]) -> int:
    """
    诊断环境并运行
    
    Args:
        args: 命令行参数
    
    Returns:
        退出码
    """
    print_banner()
    
    # 1. 检查 Python 版本
    print_info("检查 Python 环境...")
    if not check_python_env():
        print_error(
            "Python 版本过低",
            f"当前版本: Python {sys.version_info.major}.{sys.version_info.minor}\n"
            f"最低要求: Python 3.8\n"
            f"请升级 Python 后重试"
        )
        return 1
    
    print_info(f"Python 版本: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    # 2. 检查核心依赖
    print_info("检查核心依赖...")
    deps_ok, missing_deps = check_dependencies()
    
    if not deps_ok:
        print_error(
            "缺少必要依赖",
            f"缺失的包: {', '.join(missing_deps)}\n"
            f"请运行: pip install {' '.join(missing_deps)}"
        )
        return 1
    
    print_info("核心依赖完整")
    
    # 3. 检查网络
    print_info("检查网络连接...")
    network_ok = check_network()
    
    if not network_ok:
        print_warning(
            "网络连接失败",
            "无法访问互联网,将使用离线模式\n"
            "以下功能将不可用:\n"
            "  - PaddleX API\n"
            "  - LLM 语义提取\n"
            "  - Web 搜索补全影响因子"
        )
        
        # 检查本地 OCR
        print_info("检查本地 OCR 环境...")
        if check_paddleocr():
            print_info("本地 PaddleOCR 可用,将使用本地 OCR 处理扫描版 PDF")
        else:
            print_warning(
                "本地 PaddleOCR 未安装",
                "扫描版 PDF 将无法处理\n"
                "如需处理扫描版 PDF,请安装: pip install paddlepaddle paddleocr"
            )
    else:
        print_info("网络连接正常")
        
        # 检查本地 OCR (作为备用)
        if check_paddleocr():
            print_info("本地 PaddleOCR 可用 (作为备用)")
    
    # 4. 运行环境检查报告
    print()
    print_info("生成环境检查报告...")
    
    try:
        from paperinsight.utils.env_checker import EnvironmentChecker
        
        checker = EnvironmentChecker()
        all_ok, results = checker.check_all()
        checker.print_report()
        
        # 获取推荐模式
        mode = checker.get_recommendation()
        
        if mode == "offline_basic":
            print_warning(
                "当前处于离线模式且无本地 OCR",
                "仅能处理包含文本层的 PDF 文件\n"
                "扫描版 PDF 将被跳过"
            )
    
    except Exception as e:
        print_warning(f"环境检查失败: {e}")
    
    # 5. 启动应用
    print()
    print("=" * 60)
    print("  启动 PaperInsight...")
    print("=" * 60)
    print()
    
    return run_with_python(args)


def main():
    """主入口"""
    args = sys.argv[1:]
    return diagnose_and_run(args)


if __name__ == "__main__":
    sys.exit(main())
