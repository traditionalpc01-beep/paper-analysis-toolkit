"""
CLI 入口模块 v3.0

========================================
重要：启动流程说明（必须按顺序执行）
========================================

PaperInsight 遵循严格的启动流程，确保系统正确初始化：

┌─────────────────────────────────────────────────────────────┐
│  【第一步】环境自检 (Environment Check)                      │
│  ─────────────────────────────────────────────────────────  │
│  检查项目：                                                  │
│  • Python 版本 >= 3.9                                       │
│  • 核心依赖：typer, rich, PyMuPDF, openpyxl, pydantic       │
│  • 配置文件完整性                                            │
│  • API Key 是否已配置                                        │
│                                                             │
│  如果检测到缺失：                                            │
│  → 自动提示用户进入配置向导                                  │
│  → 用户可选择跳过（使用基础模式）                            │
├─────────────────────────────────────────────────────────────┤
│  【第二步】模式选择 (Mode Selection)                         │
│  ─────────────────────────────────────────────────────────  │
│  可选模式：                                                  │
│  • 智能 API 模式：调用 LLM + OCR API（需配置 API Key）       │
│  • 基础正则模式：本地正则提取（免费，无需配置）              │
│  • 自动模式：根据配置自动选择（默认）                        │
├─────────────────────────────────────────────────────────────┤
│  【第三步】任务输入 (Task Input)                             │
│  ─────────────────────────────────────────────────────────  │
│  支持方式：                                                  │
│  • 命令行参数：paperinsight analyze ./pdfs                  │
│  • 交互式输入：直接拖拽文件夹到终端                          │
│  • 路径输入：支持绝对路径和相对路径                          │
└─────────────────────────────────────────────────────────────┘

推荐使用方式：
  新用户：paperinsight check → paperinsight config → paperinsight analyze
  老用户：paperinsight analyze ./pdfs（自动执行完整流程）
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt, Confirm
from rich.table import Table

from paperinsight import __version__
from paperinsight.core.pipeline import AnalysisPipeline
from paperinsight.utils.config import DEFAULT_CONFIG, load_config, save_config
from paperinsight.utils.config_wizard import ConfigWizard

app = typer.Typer(
    name="paperinsight",
    help="智能科研论文分析工具 v3.0 - 自动提取 PDF 论文关键信息",
    add_completion=False,
)

console = Console()


# ============================================================================
# 【第一步】环境自检
# ============================================================================

def _check_config_status(config: dict) -> tuple[bool, list[str]]:
    """
    检查配置状态
    
    Returns:
        (是否完整, 缺失项列表)
    """
    missing = []
    
    # 检查 LLM 配置
    llm_config = config.get("llm", {})
    if llm_config.get("enabled", False):
        provider = llm_config.get("provider", "")
        if provider == "wenxin":
            wenxin = llm_config.get("wenxin", {})
            if not wenxin.get("client_id") or not wenxin.get("client_secret"):
                missing.append("文心一言 Client ID/Secret")
        else:
            if not llm_config.get("api_key"):
                missing.append(f"{provider.upper()} API Key")
    
    # 检查 MinerU API 模式
    mineru_config = config.get("mineru", {})
    if mineru_config.get("enabled") and mineru_config.get("mode") == "api":
        if not mineru_config.get("token"):
            missing.append("MinerU API Token")
    
    # 检查 PaddleX API
    paddlex_config = config.get("paddlex", {})
    if paddlex_config.get("enabled", False):
        if not paddlex_config.get("token"):
            missing.append("PaddleX Token")
    
    return len(missing) == 0, missing


def _has_online_capability(config: dict) -> bool:
    """检查是否有在线能力（MinerU API 或 LLM）"""
    return any(
        [
            config.get("mineru", {}).get("enabled", False) and config.get("mineru", {}).get("mode") == "api",
            config.get("paddlex", {}).get("enabled", False),
            config.get("llm", {}).get("enabled", False),
        ]
    )


def _run_startup_checks(config: dict, allow_config_wizard: bool = True) -> bool:
    """
    【第一步】启动时环境自检
    
    检查顺序：
    1. Python 版本
    2. 核心依赖
    3. 配置完整性
    4. 显示可用能力
    
    Returns:
        是否通过自检
    """
    console.print("\n" + "=" * 60)
    console.print("[bold cyan]【第一步】环境自检[/bold cyan]")
    console.print("=" * 60)
    
    # 1. 检查 Python 版本
    console.print("\n[1/4] 检查 Python 版本...")
    import sys
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info < (3, 9):
        console.print(f"  [red]✗ Python 版本过低 ({py_version})，需要 3.9 或更高版本[/red]")
        return False
    console.print(f"  [green]✓[/green] Python 版本: {py_version}")
    
    # 2. 检查核心依赖
    console.print("\n[2/4] 检查核心依赖...")
    missing_deps = []
    core_deps = [
        ("typer", "typer"),
        ("rich", "rich"),
        ("fitz", "PyMuPDF"),
        ("openpyxl", "openpyxl"),
        ("pydantic", "pydantic"),
    ]
    for module, package in core_deps:
        try:
            __import__(module)
            console.print(f"  [green]✓[/green] {package}")
        except ImportError:
            console.print(f"  [red]✗[/red] {package} (缺失)")
            missing_deps.append(package)
    
    if missing_deps:
        console.print(f"\n[red]缺少核心依赖: {', '.join(missing_deps)}[/red]")
        console.print(f"[yellow]请运行: pip install {' '.join(missing_deps)}[/yellow]")
        return False
    
    # 3. 检查配置完整性
    console.print("\n[3/4] 检查配置完整性...")
    is_complete, missing = _check_config_status(config)
    
    if not is_complete:
        console.print(f"  [yellow]⚠ 检测到以下配置缺失:[/yellow]")
        for item in missing:
            console.print(f"      - {item}")
        
        # 提示是否进入配置向导
        if allow_config_wizard:
            if Confirm.ask("\n  是否立即配置？", default=True):
                console.print("\n[dim]→ 进入配置向导...[/dim]")
                wizard = ConfigWizard()
                if not wizard.run():
                    return False
                # 重新加载配置
                config = load_config()
                is_complete = True
            else:
                console.print("  [yellow]将使用基础正则模式运行[/yellow]")
    else:
        console.print("  [green]✓ 配置完整[/green]")
    
    # 4. 显示可用能力
    console.print("\n[4/4] 检测可用能力...")
    
    llm_config = config.get("llm", {})
    if llm_config.get("enabled"):
        provider = llm_config.get("provider", "")
        console.print(f"  [green]✓[/green] LLM 语义提取: {provider}")
    else:
        console.print("  [yellow]○[/yellow] LLM 语义提取: 未配置")
    
    mineru_config = config.get("mineru", {})
    if mineru_config.get("enabled"):
        mode = mineru_config.get("mode", "cli")
        console.print(f"  [green]✓[/green] MinerU 解析: {mode} 模式")
    else:
        console.print("  [yellow]○[/yellow] MinerU 解析: 未启用")
    
    paddlex_config = config.get("paddlex", {})
    if paddlex_config.get("enabled"):
        console.print("  [green]✓[/green] PaddleX OCR: 已配置")
    else:
        console.print("  [yellow]○[/yellow] PaddleX OCR: 未配置")
    
    web_config = config.get("web_search", {})
    if web_config.get("enabled"):
        console.print("  [green]✓[/green] Web 搜索: 已启用")
    else:
        console.print("  [yellow]○[/yellow] Web 搜索: 未启用")
    
    console.print("\n" + "-" * 60)
    console.print("[green]✓ 环境自检完成[/green]")
    console.print("-" * 60)
    return True


# ============================================================================
# 【第二步】模式选择
# ============================================================================

def _select_mode(config: dict, mode_arg: Optional[str] = None) -> str:
    """
    【第二步】选择运行模式
    
    模式说明：
    - api: 智能 API 模式，调用 LLM + OCR 进行高精度提取
    - regex: 基础正则模式，本地正则脚本极速提取（免费）
    - auto: 自动模式，根据配置智能选择
    
    Returns:
        运行模式: "api", "regex", "auto"
    """
    # 如果命令行已指定非 auto 模式，直接使用
    if mode_arg and mode_arg != "auto":
        console.print(f"\n[dim]→ 使用命令行指定模式: {mode_arg}[/dim]")
        return mode_arg
    
    # 自动模式：根据配置智能选择
    has_online = _has_online_capability(config)
    
    if mode_arg == "auto":
        selected = "api" if has_online else "regex"
        console.print(f"\n[dim]→ 自动选择模式: {selected}[/dim]")
        return selected
    
    # 交互式选择
    console.print("\n" + "=" * 60)
    console.print("[bold cyan]【第二步】选择运行模式[/bold cyan]")
    console.print("=" * 60)
    console.print("\n可选模式：")
    console.print("-" * 60)
    
    modes = {
        "1": ("api", "智能 API 模式", "调用 LLM + OCR API 进行高精度提取（消耗 API 额度）"),
        "2": ("regex", "基础正则模式", "使用本地正则脚本极速提取（免费，兜底方案）"),
    }
    
    for key, (_, name, desc) in modes.items():
        console.print(f"  [cyan]{key}[/cyan]. [bold]{name}[/bold]")
        console.print(f"      [dim]{desc}[/dim]")
    
    # 根据配置推荐默认选项
    if has_online:
        default = "1"
        console.print(f"\n[green]推荐: 智能 API 模式[/green] (已检测到 API 配置)")
    else:
        default = "2"
        console.print(f"\n[yellow]推荐: 基础正则模式[/yellow] (未检测到 API 配置)")
    
    console.print("-" * 60)
    choice = Prompt.ask("请选择", choices=list(modes.keys()), default=default)
    
    return modes[choice][0]


# ============================================================================
# 【第三步】任务输入
# ============================================================================

def _get_pdf_directory(pdf_dir_arg: Optional[Path] = None) -> Path:
    """
    【第三步】获取 PDF 目录
    
    支持方式：
    - 命令行参数直接指定
    - 交互式输入（拖拽文件夹）
    - 绝对路径和相对路径
    
    Returns:
        PDF 目录路径
    """
    # 如果命令行已指定目录
    if pdf_dir_arg:
        console.print(f"\n[dim]→ 使用命令行指定目录: {pdf_dir_arg}[/dim]")
        return pdf_dir_arg
    
    console.print("\n" + "=" * 60)
    console.print("[bold cyan]【第三步】输入 PDF 目录[/bold cyan]")
    console.print("=" * 60)
    console.print("\n请输入包含 PDF 文件的目录路径")
    console.print("[dim]提示：可以直接拖拽文件夹到终端窗口[/dim]")
    console.print("-" * 60)
    
    while True:
        path_str = Prompt.ask("PDF 目录路径")
        # 去除可能的引号（拖拽时自动添加）
        path = Path(path_str.strip().strip('"\''))
        
        if not path.exists():
            console.print(f"[red]路径不存在: {path}[/red]")
            continue
        
        if not path.is_dir():
            console.print(f"[red]路径不是目录: {path}[/red]")
            continue
        
        # 检查是否有 PDF 文件
        pdf_files = list(path.glob("*.pdf"))
        if not pdf_files:
            # 检查子目录
            sub_pdfs = list(path.rglob("*.pdf"))
            if sub_pdfs:
                console.print(f"[yellow]当前目录无 PDF，但子目录中有 {len(sub_pdfs)} 个 PDF 文件[/yellow]")
                if Confirm.ask("是否递归扫描子目录？", default=True):
                    return path
            else:
                console.print(f"[yellow]警告: 目录中没有 PDF 文件[/yellow]")
                if not Confirm.ask("是否继续？", default=False):
                    continue
        
        return path


# ============================================================================
# 辅助函数
# ============================================================================

def _print_welcome():
    """打印欢迎信息"""
    console.print(Panel.fit(
        f"[bold cyan]PaperInsight v{__version__}[/bold cyan]\n"
        "智能科研论文分析工具\n\n"
        "[dim]专为光电/半导体领域科研人员设计[/dim]",
        border_style="cyan",
    ))


def _print_startup_flow_diagram():
    """打印启动流程图"""
    console.print(Panel(
        """
[bold cyan]启动流程说明[/bold cyan]

本工具遵循严格的启动顺序，请按以下步骤操作：

[bold]新用户推荐流程：[/bold]
  [1] paperinsight check     # 检查环境
  [2] paperinsight config    # 配置 API Key
  [3] paperinsight analyze   # 开始分析

[bold]直接运行：[/bold]
  paperinsight analyze ./pdfs  # 自动执行完整流程

[bold]启动顺序：[/bold]
  第一步 → 环境自检（Python版本、依赖、配置）
  第二步 → 模式选择（API模式 / 正则模式）
  第三步 → 任务输入（PDF目录路径）
""",
        title="📋 使用指南",
        border_style="blue",
    ))


def _print_startup_guide(config: Optional[dict] = None):
    """打印启动引导"""
    config = config or load_config()

    lines = [
        "欢迎使用 PaperInsight CLI。",
        "",
        "[bold cyan]重要：请按顺序执行以下步骤[/bold cyan]",
        "",
        "  [1] paperinsight check     # 检查环境和依赖",
        "  [2] paperinsight config    # 配置 API Key",
        "  [3] paperinsight analyze   # 开始分析论文",
        "",
    ]

    llm_enabled = config.get("llm", {}).get("enabled", False)
    
    if _has_online_capability(config):
        lines.append("[green]✓ 已检测到在线能力配置，可直接使用智能 API 模式。[/green]")
    else:
        lines.append("[yellow]⚠ 当前尚未配置在线能力，将使用基础正则模式。[/yellow]")

    lines.append("\n运行 `paperinsight doctor` 查看完整诊断。")

    console.print(
        Panel(
            Markdown("\n".join(lines)),
            title="启动引导",
            border_style="blue",
        )
    )


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """应用入口回调 - 无子命令时显示帮助"""
    if ctx.invoked_subcommand is None:
        _print_welcome()
        _print_startup_flow_diagram()
        config = load_config()
        _print_startup_guide(config)
        console.print(ctx.get_help())


@app.command()
def analyze(
    pdf_dir: Optional[Path] = typer.Argument(
        None,
        help="PDF 文件所在目录（留空则交互式输入）",
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
        help="运行模式: auto(自动), api(智能API), regex(基础正则)",
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
    skip_checks: bool = typer.Option(
        False,
        "--skip-checks",
        help="跳过启动检查（快速启动，不推荐新用户使用）",
    ),
):
    """
    分析 PDF 论文并生成报告
    
    【重要】启动流程：
      第一步：环境自检 - 检查 Python、依赖、配置
      第二步：模式选择 - 选择 API 模式或正则模式
      第三步：任务输入 - 输入 PDF 目录路径
    
    示例:
        # 交互式启动（推荐新用户）
        paperinsight analyze
        
        # 直接指定目录
        paperinsight analyze ./pdfs
        
        # 指定模式和输出
        paperinsight analyze ./pdfs -r -o ./reports --mode api
    """
    # ========== 初始化 ==========
    _print_welcome()
    config = load_config()
    
    # ========== 第一步：环境自检 ==========
    if not skip_checks:
        if not _run_startup_checks(config):
            raise typer.Exit(1)
        # 重新加载配置（可能被配置向导更新）
        config = load_config()
    else:
        console.print("\n[yellow]⚠ 已跳过环境自检[/yellow]")
    
    # ========== 第二步：模式选择 ==========
    selected_mode = _select_mode(config, mode)
    
    # ========== 第三步：任务输入 ==========
    pdf_dir = _get_pdf_directory(pdf_dir)
    
    # 设置输出目录
    if output_dir is None:
        output_dir = pdf_dir / "输出结果"
    
    # ========== 准备运行配置 ==========
    paddlex_config = config.get("paddlex", {"enabled": False, "token": ""})
    llm_config = config.get("llm", {})
    web_config = config.get("web_search", {})
    cache_config = config.get("cache", {})
    output_config = config.get("output", {})
    pdf_config = config.get("pdf", {})

    # 确定是否使用 LLM
    use_llm = selected_mode == "api" and llm_config.get("enabled", False)
    use_paddlex = selected_mode == "api" and paddlex_config.get("enabled", False)
    
    # 初始化 LLM 客户端
    llm_client = None
    if use_llm:
        try:
            provider = llm_config.get("provider", "")
            if provider == "openai":
                from paperinsight.llm.openai_client import OpenAIClient
                llm_client = OpenAIClient(
                    api_key=llm_config["api_key"],
                    model=llm_config.get("model", "gpt-4o"),
                    base_url=llm_config.get("base_url") or None,
                    timeout=llm_config.get("timeout", 120),
                )
            elif provider == "deepseek":
                from paperinsight.llm.deepseek_client import DeepSeekClient
                llm_client = DeepSeekClient(
                    api_key=llm_config["api_key"],
                    model=llm_config.get("model", "deepseek-chat"),
                )
            elif provider == "wenxin":
                from paperinsight.llm.wenxin_client import WenxinClient
                wenxin = llm_config.get("wenxin", {})
                llm_client = WenxinClient(
                    client_id=wenxin.get("client_id"),
                    client_secret=wenxin.get("client_secret"),
                    model=llm_config.get("model", "ernie-4.0-8k"),
                )
            console.print(f"\n[green]✓ LLM 已启用: {provider}[/green]")
        except Exception as e:
            console.print(f"\n[red]✗ LLM 初始化失败: {e}[/red]")
            use_llm = False

    if rename_pdfs is None:
        rename_pdfs = output_config.get("rename_pdfs", False)
    
    # ========== 显示运行配置摘要 ==========
    console.print("\n" + "=" * 60)
    console.print("[bold cyan]运行配置摘要[/bold cyan]")
    console.print("=" * 60)
    console.print(f"  PDF 目录:    {pdf_dir}")
    console.print(f"  输出目录:    {output_dir}")
    console.print(f"  递归扫描:    {'是' if recursive else '否'}")
    console.print(f"  运行模式:    {selected_mode}")
    console.print(f"  LLM 提取:    {'启用' if use_llm else '禁用'}")
    console.print(f"  PaddleX OCR: {'启用' if use_paddlex else '禁用'}")
    console.print(f"  Web 搜索:    {'启用' if web_config.get('enabled') else '禁用'}")
    console.print(f"  缓存:        {'禁用' if no_cache else '启用'}")
    console.print(f"  重命名 PDF:  {'启用' if rename_pdfs else '禁用'}")
    console.print("=" * 60)
    
    # 确认执行
    if not Confirm.ask("\n开始分析？", default=True):
        console.print("[yellow]已取消[/yellow]")
        raise typer.Exit(0)
    
    # ========== 执行分析 ==========
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
    
    # ========== 显示结果 ==========
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
    
    运行交互式配置向导，设置 LLM、OCR 等服务。
    这是启动流程中的【推荐第二步】。
    """
    _print_welcome()
    console.print("\n[bold cyan]启动配置向导[/bold cyan]")
    console.print("-" * 60)
    wizard = ConfigWizard()
    wizard.run(force=True)


@app.command()
def version():
    """显示版本信息"""
    console.print(f"PaperInsight CLI v{__version__}")


@app.command()
def doctor():
    """
    完整环境诊断
    
    执行全面的环境检测，包括:
    - Python 版本
    - 核心依赖
    - 网络连接
    - API 配置状态
    - 推荐运行模式
    """
    _print_welcome()
    config = load_config()
    _run_startup_checks(config, allow_config_wizard=False)
    
    # 额外诊断
    console.print("\n[bold cyan]附加诊断[/bold cyan]")
    console.print("-" * 60)
    
    # 网络诊断
    try:
        import requests
        console.print("[cyan]测试网络连接...[/cyan]")
        response = requests.head("https://www.baidu.com", timeout=5)
        console.print("  [green]✓[/green] 网络连接正常")
    except Exception as e:
        console.print(f"  [yellow]![/yellow] 网络连接失败: {e}")
    
    # 推荐模式
    console.print("\n[bold]推荐运行模式:[/bold]")
    if _has_online_capability(config):
        console.print("  [green]→ 智能 API 模式[/green] (已配置 API)")
    else:
        console.print("  [yellow]→ 基础正则模式[/yellow] (未配置 API)")
        console.print("  [dim]建议运行: paperinsight config[/dim]")


@app.command()
def check():
    """
    快速环境检查
    
    这是启动流程中的【推荐第一步】。
    只检查必要条件，适合快速验证。
    """
    _print_welcome()
    
    console.print("[bold cyan]快速环境检查[/bold cyan]")
    console.print("=" * 60)
    
    # 检查 Python
    console.print("\n[1/4] Python 版本...")
    import sys
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    console.print(f"  Python 版本: {py_version}")
    
    if sys.version_info < (3, 9):
        console.print("[red]✗ Python 版本过低，需要 3.9 或更高版本[/red]")
        raise typer.Exit(1)
    
    console.print("[green]✓ Python 版本正常[/green]")
    
    # 检查依赖
    console.print("\n[2/4] 核心依赖...")
    missing = []
    required = [
        ("typer", "typer"),
        ("rich", "rich"),
        ("fitz", "PyMuPDF"),
        ("openpyxl", "openpyxl"),
        ("pydantic", "pydantic"),
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
    
    # 检查网络
    console.print("\n[3/4] 网络连接...")
    try:
        import requests
        response = requests.head("https://www.baidu.com", timeout=5)
        console.print("  [green]✓[/green] 网络连接正常")
        network_ok = True
    except Exception:
        console.print("  [yellow]![/yellow] 网络连接失败 (离线模式)")
        network_ok = False
    
    # 检查配置
    console.print("\n[4/4] 配置状态...")
    config = load_config()
    is_complete, missing_config = _check_config_status(config)
    
    if is_complete:
        console.print("  [green]✓[/green] 配置完整")
    else:
        console.print(f"  [yellow]![/yellow] 配置缺失: {', '.join(missing_config)}")
    
    # 总结
    console.print("\n" + "=" * 60)
    
    if is_complete:
        console.print("[bold green]✓ 环境检查通过[/bold green]")
        console.print("\n下一步:")
        console.print("  paperinsight analyze ./pdfs")
    elif network_ok:
        console.print("[bold yellow]⚠ 环境可用（部分配置缺失）[/bold yellow]")
        console.print("\n建议按顺序执行:")
        console.print("  [1] paperinsight config")
        console.print("  [2] paperinsight analyze ./pdfs")
    else:
        console.print("[bold yellow]⚠ 离线模式可用[/bold yellow]")
        console.print("\n可以运行:")
        console.print("  paperinsight analyze ./pdfs")


@app.command()
def cache_info():
    """显示缓存信息"""
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
    """清除所有缓存"""
    from paperinsight.core.cache import CacheManager
    
    cache_manager = CacheManager()
    cache_manager.clear_cache()
    console.print("[green]缓存已清除[/green]")


if __name__ == "__main__":
    app()
