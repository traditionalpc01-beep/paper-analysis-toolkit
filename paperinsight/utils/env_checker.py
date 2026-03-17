"""
环境检测模块
功能: 检测运行环境、网络连接、Python 环境
"""

import platform
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from paperinsight.utils.config import load_config
from paperinsight.utils.terminal import create_console


class EnvironmentStatus(Enum):
    """环境状态"""
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class CheckResult:
    """检测结果"""
    status: EnvironmentStatus
    message: str
    details: Optional[str] = None


class EnvironmentChecker:
    """环境检测器"""
    
    def __init__(self):
        self.results: dict[str, CheckResult] = {}
        self.platform = platform.system()
        self.python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    
    def check_all(self) -> tuple[bool, dict[str, CheckResult]]:
        """
        执行所有检查
        
        Returns:
            (是否全部通过, 检查结果字典)
        """
        self.results = {}
        
        # 1. 检查 Python 版本
        self._check_python_version()
        
        # 2. 检查网络连接
        self._check_network()

        # 3. 检查 PaddleX API 配置
        self._check_paddlex_config()

        # 4. 检查 LLM API 配置
        self._check_llm_config()
        
        # 5. 检查本地 OCR 环境
        self._check_local_ocr()
        
        # 6. 检查 PDF 处理依赖
        self._check_pdf_dependencies()
        
        # 判断整体状态
        has_error = any(r.status == EnvironmentStatus.ERROR for r in self.results.values())
        
        return not has_error, self.results
    
    def _check_python_version(self):
        """检查 Python 版本"""
        min_version = (3, 8)
        current = (sys.version_info.major, sys.version_info.minor)
        
        if current >= min_version:
            self.results["python_version"] = CheckResult(
                status=EnvironmentStatus.OK,
                message=f"Python 版本: {self.python_version}",
                details=f"最低要求: Python {min_version[0]}.{min_version[1]}",
            )
        else:
            self.results["python_version"] = CheckResult(
                status=EnvironmentStatus.ERROR,
                message=f"Python 版本过低: {self.python_version}",
                details=f"请升级到 Python {min_version[0]}.{min_version[1]} 或更高版本",
            )
    
    def _check_network(self):
        """检查网络连接"""
        test_urls = [
            ("百度 AI Studio", "https://aistudio.baidu.com"),
            ("OpenAI", "https://api.openai.com"),
            ("DeepSeek", "https://api.deepseek.com"),
        ]
        
        available = []
        failed = []
        
        for name, url in test_urls:
            try:
                import requests
                response = requests.head(url, timeout=5, allow_redirects=True)
                if response.status_code < 500:
                    available.append(name)
                else:
                    failed.append(name)
            except Exception:
                failed.append(name)
        
        if available:
            self.results["network"] = CheckResult(
                status=EnvironmentStatus.OK if not failed else EnvironmentStatus.WARNING,
                message=f"网络连接正常: {', '.join(available)}",
                details=f"无法访问: {', '.join(failed)}" if failed else None,
            )
        else:
            self.results["network"] = CheckResult(
                status=EnvironmentStatus.ERROR,
                message="网络连接失败",
                details="无法访问任何测试站点,请检查网络设置",
            )
    
    def _check_paddlex_config(self):
        """检查 PaddleX API 配置"""
        config = load_config()

        paddlex_config = config.get("paddlex", {})
        enabled = paddlex_config.get("enabled", False)
        token = paddlex_config.get("token", "")

        if not enabled:
            self.results["paddlex"] = CheckResult(
                status=EnvironmentStatus.WARNING,
                message="PaddleX API 未启用",
                details="将在需要时使用本地 OCR",
            )
            return

        if not token:
            self.results["paddlex"] = CheckResult(
                status=EnvironmentStatus.ERROR,
                message="PaddleX 配置不完整",
                details="请配置 PaddleX Token",
            )
            return

        self.results["paddlex"] = CheckResult(
            status=EnvironmentStatus.OK,
            message="PaddleX 配置有效",
        )

    def _check_llm_config(self):
        """检查 LLM API 配置"""
        config = load_config()
        
        llm_config = config.get("llm", {})
        enabled = llm_config.get("enabled", False)
        provider = llm_config.get("provider", "")
        api_key = llm_config.get("api_key", "")
        
        if not enabled:
            self.results["llm"] = CheckResult(
                status=EnvironmentStatus.WARNING,
                message="LLM 未启用",
                details="将使用正则表达式提取数据",
            )
            return
        
        if not api_key:
            self.results["llm"] = CheckResult(
                status=EnvironmentStatus.ERROR,
                message=f"{provider.upper()} API Key 未配置",
                details="请配置 API Key",
            )
            return
        
        self.results["llm"] = CheckResult(
            status=EnvironmentStatus.OK,
            message=f"{provider.upper()} LLM 配置有效",
        )
    
    def _check_local_ocr(self):
        """检查本地 OCR 环境"""
        try:
            import paddleocr
            import paddle
            
            self.results["local_ocr"] = CheckResult(
                status=EnvironmentStatus.OK,
                message="本地 PaddleOCR 可用",
                details="可作为 OCR 兜底方案",
            )
        except ImportError:
            self.results["local_ocr"] = CheckResult(
                status=EnvironmentStatus.WARNING,
                message="本地 PaddleOCR 未安装",
                details="安装命令: pip install paddlepaddle paddleocr",
            )
    
    def _check_pdf_dependencies(self):
        """检查 PDF 处理依赖"""
        missing = []
        
        try:
            import fitz  # PyMuPDF
        except ImportError:
            missing.append("PyMuPDF")
        
        try:
            import openpyxl
        except ImportError:
            missing.append("openpyxl")
        
        try:
            import typer
        except ImportError:
            missing.append("typer")
        
        try:
            import rich
        except ImportError:
            missing.append("rich")
        
        if missing:
            self.results["pdf_deps"] = CheckResult(
                status=EnvironmentStatus.ERROR,
                message="缺少必要依赖",
                details=f"请安装: pip install {' '.join(missing)}",
            )
        else:
            self.results["pdf_deps"] = CheckResult(
                status=EnvironmentStatus.OK,
                message="PDF 处理依赖完整",
            )
    
    def get_recommendation(self) -> str:
        """
        根据检查结果给出运行建议
        
        Returns:
            推荐的运行模式
        """
        network_ok = self.results.get("network", CheckResult(EnvironmentStatus.ERROR, "")).status != EnvironmentStatus.ERROR
        paddlex_ok = self.results.get("paddlex", CheckResult(EnvironmentStatus.ERROR, "")).status == EnvironmentStatus.OK
        llm_ok = self.results.get("llm", CheckResult(EnvironmentStatus.ERROR, "")).status == EnvironmentStatus.OK
        local_ocr_ok = self.results.get("local_ocr", CheckResult(EnvironmentStatus.ERROR, "")).status == EnvironmentStatus.OK
        
        if not network_ok:
            if local_ocr_ok:
                return "offline_local"  # 离线模式,使用本地 OCR
            else:
                return "offline_basic"  # 离线模式,仅基础正则
        
        if paddlex_ok and llm_ok:
            return "api"  # 智能 API 模式
        elif paddlex_ok:
            return "ocr_api"  # 仅 OCR API 模式
        elif llm_ok:
            return "llm_api"  # 仅 LLM API 模式
        elif local_ocr_ok:
            return "local"  # 本地 OCR 模式
        else:
            return "basic"  # 基础正则模式
    
    def print_report(self):
        """打印检查报告"""
        from rich.table import Table

        console = create_console()
        
        console.print("\n[bold]PaperInsight 环境检测报告[/bold]\n")
        
        table = Table(show_header=True, header_style="bold")
        table.add_column("检查项", style="cyan")
        table.add_column("状态", width=10)
        table.add_column("说明")
        
        status_style = {
            EnvironmentStatus.OK: "green",
            EnvironmentStatus.WARNING: "yellow",
            EnvironmentStatus.ERROR: "red",
        }
        
        for name, result in self.results.items():
            status_text = {
                EnvironmentStatus.OK: "✓ 正常",
                EnvironmentStatus.WARNING: "⚠ 警告",
                EnvironmentStatus.ERROR: "✗ 错误",
            }[result.status]
            
            table.add_row(
                name,
                f"[{status_style[result.status]}]{status_text}[/{status_style[result.status]}]",
                result.message,
            )
        
        console.print(table)
        
        # 打印详细信息
        for name, result in self.results.items():
            if result.details:
                console.print(f"  [dim]{name}: {result.details}[/dim]")
        
        # 打印建议
        recommendation = self.get_recommendation()
        recommendation_text = {
            "api": "智能 API 模式 (推荐)",
            "ocr_api": "OCR API 模式",
            "llm_api": "LLM API 模式",
            "local": "本地 OCR 模式",
            "offline_local": "离线模式 - 本地 OCR",
            "offline_basic": "离线模式 - 基础正则",
            "basic": "基础正则模式",
        }.get(recommendation, "基础模式")
        
        console.print(f"\n[bold]推荐运行模式:[/bold] {recommendation_text}")
        console.print()


def check_environment() -> tuple[bool, dict]:
    """
    检查环境
    
    Returns:
        (是否可以运行, 检查结果)
    """
    checker = EnvironmentChecker()
    return checker.check_all()


def get_run_mode() -> str:
    """
    获取推荐的运行模式
    
    Returns:
        运行模式
    """
    checker = EnvironmentChecker()
    checker.check_all()
    return checker.get_recommendation()
