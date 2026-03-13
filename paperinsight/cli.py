"""
CLI 入口模块
功能: 命令行接口
"""

import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table

from paperinsight import __version__
from paperinsight.core.pipeline import AnalysisPipeline
from paperinsight.utils.config_crypto import (
    decrypt_sensitive_fields,
    encrypt_sensitive_fields,
)

app = typer.Typer(
    name="paperinsight",
    help="智能科研论文分析工具 - 自动提取 PDF 论文关键信息",
    add_completion=False,
)

console = Console()


def get_config_path() -> Path:
    """获取配置文件路径"""
    config_dir = Path.home() / ".paperinsight"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.yaml"


def load_config() -> dict:
    """加载配置(自动解密敏感字段)"""
    import yaml
    
    config_path = get_config_path()
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
            # 解密敏感字段
            return decrypt_sensitive_fields(config)
    return {}


def save_config(config: dict):
    """保存配置(自动加密敏感字段)"""
    import yaml
    
    config_path = get_config_path()
    # 加密敏感字段
    encrypted_config = encrypt_sensitive_fields(config)
    
    with config_path.open("w", encoding="utf-8") as f:
        yaml.dump(encrypted_config, f, default_flow_style=False, allow_unicode=True)
    
    # 设置文件权限(仅当前用户可读写)
    import os
    os.chmod(config_path, 0o600)


def interactive_config() -> dict:
    """交互式配置引导"""
    console.print(Panel.fit(
        "[bold blue]PaperInsight 配置向导[/bold blue]\n\n"
        "首次运行,请配置必要的 API Key",
        title="欢迎",
        border_style="blue",
    ))
    
    config = {}
    
    # 百度 OCR 配置
    use_baidu = Prompt.ask(
        "是否使用百度 OCR API?",
        choices=["y", "n"],
        default="n",
    )
    if use_baidu == "y":
        config["use_baidu_ocr"] = True
        config["baidu_api_key"] = Prompt.ask("请输入百度 API Key")
        config["baidu_secret_key"] = Prompt.ask("请输入百度 Secret Key")
    else:
        config["use_baidu_ocr"] = False
    
    # LLM 配置
    use_llm = Prompt.ask(
        "是否使用 LLM 进行语义提取?",
        choices=["y", "n"],
        default="n",
    )
    if use_llm == "y":
        config["use_llm"] = True
        llm_provider = Prompt.ask(
            "选择 LLM 提供商",
            choices=["openai", "deepseek"],
            default="openai",
        )
        config["llm_provider"] = llm_provider
        config["llm_api_key"] = Prompt.ask(f"请输入 {llm_provider.upper()} API Key")
        if llm_provider == "openai":
            config["llm_model"] = Prompt.ask(
                "模型名称",
                default="gpt-4o",
            )
        else:
            config["llm_model"] = Prompt.ask(
                "模型名称",
                default="deepseek-chat",
            )
    else:
        config["use_llm"] = False
    
    # Web 搜索配置
    use_web = Prompt.ask(
        "是否启用 Web 搜索补全影响因子?",
        choices=["y", "n"],
        default="y",
    )
    config["use_web_search"] = (use_web == "y")
    
    # 保存配置
    save_config(config)
    console.print("\n[green]配置已保存![/green]\n")
    
    return config


@app.command()
def analyze(
    pdf_dir: Path = typer.Argument(
        ...,
        help="PDF 文件所在目录",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="输出目录(默认为 PDF 目录下的 '输出结果' 文件夹)",
    ),
    recursive: bool = typer.Option(
        False,
        "--recursive", "-r",
        help="递归扫描子目录",
    ),
    max_pages: int = typer.Option(
        0,
        "--max-pages",
        help="每篇论文最大读取页数(0 表示不限制)",
    ),
    mode: str = typer.Option(
        "auto",
        "--mode", "-m",
        help="运行模式: auto(自动), api(智能 API), regex(基础正则)",
    ),
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="禁用缓存",
    ),
    export_json: bool = typer.Option(
        False,
        "--json",
        help="同时导出 JSON 报告",
    ),
):
    """
    分析 PDF 论文并生成报告
    
    示例:
        paperinsight analyze ./pdfs
        paperinsight analyze ./pdfs --recursive --output ./reports
        paperinsight analyze ./pdfs --mode api --max-pages 10
    """
    # 显示欢迎信息
    console.print(Panel.fit(
        f"[bold blue]PaperInsight CLI v{__version__}[/bold blue]\n"
        f"智能科研论文分析工具",
        border_style="blue",
    ))
    
    # 加载配置
    config = load_config()
    
    # 如果没有配置,启动交互式配置
    if not config and mode == "api":
        config = interactive_config()
    
    # 设置输出目录
    if output_dir is None:
        output_dir = pdf_dir / "输出结果"
    
    # 确定运行模式
    if mode == "regex":
        use_baidu_ocr = False
        use_llm = False
    elif mode == "api":
        use_baidu_ocr = config.get("use_baidu_ocr", False)
        use_llm = config.get("use_llm", False)
    else:  # auto
        use_baidu_ocr = config.get("use_baidu_ocr", False)
        use_llm = config.get("use_llm", False)
    
    # 初始化 LLM 客户端
    llm_client = None
    if use_llm:
        try:
            if config.get("llm_provider") == "openai":
                from paperinsight.llm.openai_client import OpenAIClient
                llm_client = OpenAIClient(
                    api_key=config["llm_api_key"],
                    model=config.get("llm_model", "gpt-4o"),
                )
            elif config.get("llm_provider") == "deepseek":
                from paperinsight.llm.deepseek_client import DeepSeekClient
                llm_client = DeepSeekClient(
                    api_key=config["llm_api_key"],
                    model=config.get("llm_model", "deepseek-chat"),
                )
            console.print(f"[green]LLM 已启用: {config.get('llm_provider')}[/green]")
        except Exception as e:
            console.print(f"[red]LLM 初始化失败: {e}[/red]")
            use_llm = False
    
    # 显示配置信息
    console.print(f"\n[cyan]PDF 目录:[/cyan] {pdf_dir}")
    console.print(f"[cyan]输出目录:[/cyan] {output_dir}")
    console.print(f"[cyan]运行模式:[/cyan] {mode}")
    console.print(f"[cyan]百度 OCR:[/cyan] {'启用' if use_baidu_ocr else '禁用'}")
    console.print(f"[cyan]LLM 提取:[/cyan] {'启用' if use_llm else '禁用'}")
    console.print(f"[cyan]Web 搜索:[/cyan] {'启用' if config.get('use_web_search') else '禁用'}")
    console.print(f"[cyan]缓存:[/cyan] {'禁用' if no_cache else '启用'}")
    console.print()
    
    # 创建分析管线
    pipeline = AnalysisPipeline(
        output_dir=output_dir,
        use_baidu_ocr=use_baidu_ocr,
        baidu_api_key=config.get("baidu_api_key"),
        baidu_secret_key=config.get("baidu_secret_key"),
        use_llm=use_llm,
        llm_client=llm_client,
        use_web_search=config.get("use_web_search", False),
        enable_cache=not no_cache,
    )
    
    # 运行分析
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("分析中...", total=None)
        
        stats = pipeline.run(
            pdf_dir=pdf_dir,
            recursive=recursive,
            max_pages=max_pages if max_pages > 0 else None,
            use_cache=not no_cache,
            generate_json=export_json,
        )
    
    # 显示结果
    console.print()
    if stats["status"] == "completed":
        table = Table(title="分析统计")
        table.add_column("指标", style="cyan")
        table.add_column("数值", style="green")
        table.add_row("总文件数", str(stats["pdf_count"]))
        table.add_row("成功处理", str(stats["success_count"]))
        table.add_row("失败", str(stats["error_count"]))
        console.print(table)
        
        if stats.get("report_files"):
            console.print("\n[bold]生成的报告:[/bold]")
            for report_type, path in stats["report_files"].items():
                console.print(f"  - {report_type}: {path}")
    else:
        console.print("[red]未找到 PDF 文件[/red]")


@app.command()
def config():
    """
    配置 API Key 和其他设置
    """
    interactive_config()


@app.command()
def version():
    """
    显示版本信息
    """
    console.print(f"PaperInsight CLI v{__version__}")


@app.command()
def doctor():
    """
    检查运行环境和配置
    
    执行全面的环境检测,包括:
    - Python 版本
    - 网络连接
    - API 配置
    - 依赖完整性
    """
    console.print(Panel.fit(
        "[bold blue]PaperInsight 环境检测[/bold blue]\n\n"
        "正在检查运行环境...",
        title="诊断",
        border_style="blue",
    ))
    
    try:
        from paperinsight.utils.env_checker import EnvironmentChecker
        
        checker = EnvironmentChecker()
        all_ok, results = checker.check_all()
        checker.print_report()
        
        # 显示最终状态
        if all_ok:
            console.print("[bold green]✓ 所有检查通过,环境配置正确[/bold green]\n")
        else:
            console.print("[bold yellow]⚠ 部分检查未通过,请根据提示修复[/bold yellow]\n")
        
        # 显示推荐模式
        mode = checker.get_recommendation()
        mode_names = {
            "api": "智能 API 模式 (推荐)",
            "ocr_api": "OCR API 模式",
            "llm_api": "LLM API 模式",
            "local": "本地 OCR 模式",
            "offline_local": "离线模式 - 本地 OCR",
            "offline_basic": "离线模式 - 基础正则",
            "basic": "基础正则模式",
        }
        mode_name = mode_names.get(mode, "基础模式")
        console.print(f"[bold]推荐运行模式:[/bold] {mode_name}")
        
    except Exception as e:
        console.print(f"[red]环境检测失败: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def check():
    """
    快速检查是否可以正常运行
    
    只检查必要条件,适合快速验证
    """
    console.print("[cyan]检查 Python 环境...[/cyan]")
    
    import sys
    console.print(f"  Python 版本: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    if sys.version_info < (3, 8):
        console.print("[red]✗ Python 版本过低,需要 3.8 或更高版本[/red]")
        raise typer.Exit(1)
    
    console.print("[green]✓ Python 版本正常[/green]")
    
    console.print("\n[cyan]检查核心依赖...[/cyan]")
    
    missing = []
    required = [
        ("typer", "typer"),
        ("rich", "rich"),
        ("fitz", "PyMuPDF"),
        ("openpyxl", "openpyxl"),
    ]
    
    for module, package in required:
        try:
            __import__(module)
            console.print(f"  [green]✓[/green] {package}")
        except ImportError:
            console.print(f"  [red]✗[/red] {package}")
            missing.append(package)
    
    if missing:
        console.print(f"\n[red]缺少依赖: {', '.join(missing)}[/red]")
        console.print(f"[yellow]请运行: pip install {' '.join(missing)}[/yellow]")
        raise typer.Exit(1)
    
    console.print("\n[cyan]检查网络连接...[/cyan]")
    
    try:
        import requests
        response = requests.head("https://www.baidu.com", timeout=5)
        console.print("  [green]✓[/green] 网络连接正常")
        network_ok = True
    except Exception:
        console.print("  [yellow]![/yellow] 网络连接失败 (离线模式)")
        network_ok = False
    
    console.print("\n[cyan]检查本地 OCR...[/cyan]")
    
    try:
        import paddleocr
        import paddle
        console.print("  [green]✓[/green] PaddleOCR 可用")
        local_ocr = True
    except ImportError:
        console.print("  [yellow]![/yellow] PaddleOCR 未安装")
        local_ocr = False
    
    # 总结
    console.print("\n" + "=" * 50)
    
    if network_ok:
        console.print("[bold green]✓ 环境检查通过[/bold green]")
        console.print("可以运行: paperinsight analyze ./pdfs")
    elif local_ocr:
        console.print("[bold yellow]⚠ 离线模式可用[/bold yellow]")
        console.print("可以运行: paperinsight analyze ./pdfs")
    else:
        console.print("[bold yellow]⚠ 基础模式可用[/bold yellow]")
        console.print("仅能处理包含文本层的 PDF")
        console.print("可以运行: paperinsight analyze ./pdfs")


@app.command()
def cache_info():
    """
    显示缓存信息
    """
    from paperinsight.core.cache import CacheManager
    
    cache_manager = CacheManager()
    stats = cache_manager.get_cache_stats()
    
    table = Table(title="缓存统计")
    table.add_column("指标", style="cyan")
    table.add_column("数值", style="green")
    table.add_row("数据缓存数", str(stats["data_cache_count"]))
    table.add_row("OCR 缓存数", str(stats["ocr_cache_count"]))
    table.add_row("总大小", f"{stats['total_size_mb']} MB")
    console.print(table)


@app.command()
def clear_cache():
    """
    清除所有缓存
    """
    from paperinsight.core.cache import CacheManager
    
    cache_manager = CacheManager()
    cache_manager.clear_cache()
    console.print("[green]缓存已清除[/green]")


if __name__ == "__main__":
    app()
