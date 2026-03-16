"""
CLI 入口模块
功能: 命令行接口
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table

from paperinsight import __version__
from paperinsight.core.pipeline import AnalysisPipeline
from paperinsight.utils.config import DEFAULT_CONFIG, load_config, save_config

app = typer.Typer(
    name="paperinsight",
    help="智能科研论文分析工具 - 自动提取 PDF 论文关键信息",
    add_completion=False,
)

console = Console()


def _has_online_capability(config: dict) -> bool:
    return any(
        [
            config.get("paddlex", {}).get("enabled", False),
            config.get("llm", {}).get("enabled", False),
        ]
    )


def _print_startup_guide(config: Optional[dict] = None):
    config = config or load_config()

    lines = [
        "欢迎使用 PaperInsight CLI。",
        "",
        "建议按这个顺序开始：",
        "1. 运行 `paperinsight check` 检查依赖和网络",
        "2. 运行 `paperinsight config` 配置 OCR / LLM / Web 搜索",
        "3. 运行 `paperinsight analyze ./pdfs` 开始分析",
        "",
    ]

    if _has_online_capability(config):
        lines.append("当前已检测到至少一个在线能力已配置，可直接使用 `--mode api` 或默认 `auto` 模式。")
    else:
        lines.append("当前尚未配置在线能力，直接运行时会回落到基础正则 / 本地文本提取模式。")

    lines.append("如需查看完整诊断，请运行 `paperinsight doctor`。")

    console.print(
        Panel(
            Markdown("\n".join(lines)),
            title="启动引导",
            border_style="blue",
        )
    )


def _print_mode_guidance(mode: str, config: dict):
    if mode == "regex":
        console.print(
            Panel.fit(
                "当前为基础正则模式，不会调用 OCR API 或 LLM。",
                title="运行提示",
                border_style="yellow",
            )
        )
        return

    if mode == "api" and not _has_online_capability(config):
        console.print(
            Panel.fit(
                "你选择了 `api` 模式，但还没有可用的在线 OCR / LLM 配置。\n"
                "接下来会进入配置向导；如果你想先离线试跑，可改用 `--mode regex`。",
                title="首次配置提示",
                border_style="yellow",
            )
        )
        return

    if mode == "auto" and not _has_online_capability(config):
        console.print(
            Panel.fit(
                "当前未配置在线 OCR / LLM，`auto` 模式会使用本地文本提取并在需要时尝试本地 OCR。\n"
                "如需更高精度，可先运行 `paperinsight config`。",
                title="模式说明",
                border_style="cyan",
            )
        )


def _prompt_secret(label: str, existing_value: str = "") -> str:
    prompt = f"{label} (留空则保留当前值)"
    value = Prompt.ask(prompt, password=True, default="")
    if value:
        return value
    return existing_value


def interactive_config() -> dict:
    """交互式配置引导"""
    console.print(Panel.fit(
        "[bold blue]PaperInsight 配置向导[/bold blue]\n\n"
        "按需配置 OCR、PaddleX、LLM 和 Web 搜索能力",
        title="欢迎",
        border_style="blue",
    ))
    
    config = load_config()
    paddlex_config = config.get("paddlex", {"enabled": False, "token": ""})
    llm_config = config["llm"]
    web_config = config["web_search"]
    
    # PaddleX API 配置
    use_paddlex = Prompt.ask(
        "是否使用 PaddleX API (百度AI Studio)?",
        choices=["y", "n"],
        default="y" if paddlex_config.get("enabled") else "n",
    )
    if use_paddlex == "y":
        paddlex_config["enabled"] = True
        paddlex_config["token"] = _prompt_secret(
            "请输入 PaddleX Token",
            paddlex_config.get("token", ""),
        )
        paddlex_config["model"] = Prompt.ask(
            "选择 PaddleX 模型",
            choices=["PaddleOCR-VL-1.5", "PaddleOCR-VL", "PP-StructureV3", "PP-OCRv5"],
            default=paddlex_config.get("model", "PaddleOCR-VL-1.5"),
        )
    else:
        paddlex_config["enabled"] = False

    config["paddlex"] = paddlex_config

    # LLM 配置
    use_llm = Prompt.ask(
        "是否使用 LLM 进行语义提取?",
        choices=["y", "n"],
        default="y" if llm_config.get("enabled") else "n",
    )
    if use_llm == "y":
        llm_config["enabled"] = True
        llm_provider = Prompt.ask(
            "选择 LLM 提供商",
            choices=["openai", "deepseek"],
            default=llm_config.get("provider", "openai"),
        )
        llm_config["provider"] = llm_provider
        llm_config["api_key"] = _prompt_secret(
            f"请输入 {llm_provider.upper()} API Key",
            llm_config.get("api_key", ""),
        )
        if llm_provider == "openai":
            llm_config["model"] = Prompt.ask(
                "模型名称",
                default=llm_config.get("model", "gpt-4o"),
            )
        else:
            llm_config["model"] = Prompt.ask(
                "模型名称",
                default=llm_config.get("model", "deepseek-chat"),
            )
    else:
        llm_config["enabled"] = False
    
    # Web 搜索配置
    use_web = Prompt.ask(
        "是否启用 Web 搜索补全影响因子?",
        choices=["y", "n"],
        default="y" if web_config.get("enabled") else "n",
    )
    web_config["enabled"] = (use_web == "y")
    
    # 保存配置
    save_config(config)
    console.print("\n[green]配置已保存![/green]\n")
    
    return config


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
):
    """应用入口回调。"""
    if ctx.invoked_subcommand is None:
        config = load_config()
        _print_startup_guide(config)
        console.print(ctx.get_help())


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
    rename_pdfs: Optional[bool] = typer.Option(
        None,
        "--rename-pdfs/--no-rename-pdfs",
        help="是否在分析完成后重命名 PDF 文件",
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
    _print_mode_guidance(mode, config)
    
    # 如果没有配置,启动交互式配置
    if mode == "api" and not _has_online_capability(config):
        config = interactive_config()
    
    # 设置输出目录
    if output_dir is None:
        output_dir = pdf_dir / "输出结果"
    
    paddlex_config = config.get("paddlex", {"enabled": False, "token": ""})
    llm_config = config["llm"]
    web_config = config["web_search"]
    cache_config = config["cache"]
    output_config = config["output"]
    pdf_config = config["pdf"]

    # 确定运行模式
    if mode == "regex":
        use_llm = False
    elif mode == "api":
        use_llm = llm_config.get("enabled", False)
    else:  # auto
        use_llm = llm_config.get("enabled", False)

    use_paddlex = paddlex_config.get("enabled", False)
    
    # 初始化 LLM 客户端
    llm_client = None
    if use_llm:
        try:
            if llm_config.get("provider") == "openai":
                from paperinsight.llm.openai_client import OpenAIClient
                llm_client = OpenAIClient(
                    api_key=llm_config["api_key"],
                    model=llm_config.get("model", "gpt-4o"),
                    base_url=llm_config.get("base_url") or None,
                    timeout=llm_config.get("timeout", 120),
                )
            elif llm_config.get("provider") == "deepseek":
                from paperinsight.llm.deepseek_client import DeepSeekClient
                llm_client = DeepSeekClient(
                    api_key=llm_config["api_key"],
                    model=llm_config.get("model", "deepseek-chat"),
                )
            console.print(f"[green]LLM 已启用: {llm_config.get('provider')}[/green]")
        except Exception as e:
            console.print(f"[red]LLM 初始化失败: {e}[/red]")
            use_llm = False

    if rename_pdfs is None:
        rename_pdfs = output_config.get("rename_pdfs", False)
    
    # 显示配置信息
    console.print(f"\n[cyan]PDF 目录:[/cyan] {pdf_dir}")
    console.print(f"[cyan]输出目录:[/cyan] {output_dir}")
    console.print(f"[cyan]运行模式:[/cyan] {mode}")
    console.print(f"[cyan]PaddleX OCR:[/cyan] {'启用' if use_paddlex else '禁用'}")
    console.print(f"[cyan]LLM 提取:[/cyan] {'启用' if use_llm else '禁用'}")
    console.print(f"[cyan]Web 搜索:[/cyan] {'启用' if web_config.get('enabled') else '禁用'}")
    console.print(f"[cyan]缓存:[/cyan] {'禁用' if no_cache else '启用'}")
    console.print(f"[cyan]处理后重命名:[/cyan] {'启用' if rename_pdfs else '禁用'}")
    console.print()
    
    # 创建分析管线
    pipeline = AnalysisPipeline(
        output_dir=output_dir,
        cache_dir=cache_config.get("directory", ".cache"),
        use_paddlex=use_paddlex,
        paddlex_token=paddlex_config.get("token"),
        paddlex_config=paddlex_config,
        use_llm=use_llm,
        llm_client=llm_client,
        use_web_search=web_config.get("enabled", False),
        enable_cache=cache_config.get("enabled", True) and not no_cache,
        text_ratio_threshold=pdf_config.get("text_ratio_threshold", DEFAULT_CONFIG["pdf"]["text_ratio_threshold"]),
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
            max_pages=max_pages if max_pages > 0 else (pdf_config.get("max_pages") or None),
            use_cache=cache_config.get("enabled", True) and not no_cache,
            generate_json=export_json,
            sort_by_if=output_config.get("sort_by_if", True),
            rename_pdfs=rename_pdfs,
            rename_template=output_config.get("rename_template"),
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
        if "renamed_count" in stats:
            table.add_row("重命名", str(stats["renamed_count"]))
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
