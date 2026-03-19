from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from typing import Optional
import sys
import warnings

import typer
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

from paperinsight import __version__
from paperinsight.agentflow import AgentPreparePipeline
from paperinsight.core.pipeline import AnalysisPipeline
from paperinsight.utils.config import load_config
from paperinsight.utils.config_wizard import ConfigWizard
from paperinsight.utils.terminal import create_console

app = typer.Typer(
    name="paperinsight",
    help="PaperInsight CLI - PDF paper analysis toolkit",
    add_completion=False,
)
agent_app = typer.Typer(help="Agent-first workflow helpers.")
app.add_typer(agent_app, name="agent")

console = create_console()

warnings.filterwarnings(
    "ignore",
    message=r".*urllib3 .* doesn't match a supported version!.*",
)


def _is_interactive() -> bool:
    stdin_isatty = getattr(sys.stdin, "isatty", lambda: False)()
    stdout_isatty = getattr(sys.stdout, "isatty", lambda: False)()
    return bool(stdin_isatty and stdout_isatty)


def _confirm_or_default(message: str, *, default: bool) -> bool:
    if not _is_interactive():
        console.print(f"[dim]{message} -> auto default: {'yes' if default else 'no'}[/dim]")
        return default
    return Confirm.ask(message, default=default)


def _prompt_or_default(message: str, *, default: str) -> str:
    if not _is_interactive():
        console.print(f"[dim]{message} -> auto default: {default}[/dim]")
        return default
    return Prompt.ask(message, default=default)


def _print_welcome() -> None:
    console.print(
        Panel.fit(
            f"[bold cyan]PaperInsight v{__version__}[/bold cyan]\n"
            "Smart paper analysis toolkit\n\n"
            "[dim]Windows terminal friendly mode[/dim]",
            border_style="cyan",
        )
    )


def _check_config_status(config: dict) -> tuple[bool, list[str]]:
    missing: list[str] = []

    llm_config = config.get("llm", {})
    if llm_config.get("enabled", False):
        provider = str(llm_config.get("provider", "")).lower()
        if provider == "wenxin":
            wenxin = llm_config.get("wenxin", {})
            if not wenxin.get("client_id") or not wenxin.get("client_secret"):
                missing.append("Wenxin client_id/client_secret")
        elif not llm_config.get("api_key"):
            missing.append(f"{provider or 'llm'} api_key")

    mineru_config = config.get("mineru", {})
    if mineru_config.get("enabled") and mineru_config.get("mode") == "api":
        if not mineru_config.get("token"):
            missing.append("MinerU token")

    paddlex_config = config.get("paddlex", {})
    if paddlex_config.get("enabled", False) and not paddlex_config.get("token"):
        missing.append("PaddleX token")

    return len(missing) == 0, missing


def _has_online_capability(config: dict) -> bool:
    return any(
        [
            config.get("mineru", {}).get("enabled", False)
            and config.get("mineru", {}).get("mode") == "api",
            config.get("paddlex", {}).get("enabled", False),
            config.get("llm", {}).get("enabled", False),
        ]
    )


def _run_startup_checks(config: dict, allow_config_wizard: bool = True) -> bool:
    console.print("\n" + "=" * 60)
    console.print("[bold cyan]Step 1: Environment Check[/bold cyan]")
    console.print("=" * 60)

    console.print("\n[1/4] Python version...")
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info < (3, 9):
        console.print(f"  [red][X][/red] Python version too low: {py_version} (need >= 3.9)")
        return False
    console.print(f"  [green][OK][/green] Python version: {py_version}")

    console.print("\n[2/4] Core dependencies...")
    missing_deps: list[str] = []
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
            console.print(f"  [green][OK][/green] {package}")
        except ImportError:
            console.print(f"  [red][X][/red] {package}")
            missing_deps.append(package)

    if missing_deps:
        console.print(f"\n[red]Missing dependencies:[/red] {', '.join(missing_deps)}")
        console.print(f"[yellow]Install with:[/yellow] pip install {' '.join(missing_deps)}")
        return False

    console.print("\n[3/4] Config status...")
    is_complete, missing = _check_config_status(config)
    if is_complete:
        console.print("  [green][OK][/green] Config looks complete")
    else:
        console.print("  [yellow][!][/yellow] Missing config:")
        for item in missing:
            console.print(f"      - {item}")
        if allow_config_wizard and _confirm_or_default("Open config wizard now?", default=True):
            wizard = ConfigWizard()
            if not wizard.run():
                return False
            config = load_config()
        else:
            console.print("  [yellow]Will continue with fallback mode when possible[/yellow]")

    console.print("\n[4/4] Available capabilities...")
    llm_config = config.get("llm", {})
    mineru_config = config.get("mineru", {})
    paddlex_config = config.get("paddlex", {})
    web_config = config.get("web_search", {})

    console.print(
        f"  [green][OK][/green] LLM: {llm_config.get('provider', 'disabled')}"
        if llm_config.get("enabled")
        else "  - LLM: disabled"
    )
    console.print(
        f"  [green][OK][/green] MinerU: {mineru_config.get('mode', 'cli')}"
        if mineru_config.get("enabled")
        else "  - MinerU: disabled"
    )
    console.print(
        "  [green][OK][/green] PaddleX OCR: enabled"
        if paddlex_config.get("enabled")
        else "  - PaddleX OCR: disabled"
    )
    console.print(
        "  [green][OK][/green] Web search: enabled"
        if web_config.get("enabled")
        else "  - Web search: disabled"
    )

    console.print("\n" + "-" * 60)
    console.print("[green][OK] Environment check complete[/green]")
    console.print("-" * 60)
    return True


def _select_mode(config: dict, mode_arg: Optional[str] = None) -> str:
    if mode_arg and mode_arg != "auto":
        console.print(f"\n[dim]-> using command line mode: {mode_arg}[/dim]")
        return mode_arg

    has_online = _has_online_capability(config)
    if mode_arg == "auto":
        selected = "api" if has_online else "regex"
        console.print(f"\n[dim]-> auto selected mode: {selected}[/dim]")
        return selected

    console.print("\n" + "=" * 60)
    console.print("[bold cyan]Step 2: Select Mode[/bold cyan]")
    console.print("=" * 60)
    console.print("1. api    - use LLM/OCR online services")
    console.print("2. regex  - local fallback mode")
    default = "1" if has_online else "2"
    console.print(f"\nRecommended: {'api' if has_online else 'regex'}")
    if not _is_interactive():
        return "api" if has_online else "regex"
    choice = Prompt.ask("Select mode", choices=["1", "2"], default=default)
    return "api" if choice == "1" else "regex"


def _get_pdf_directory(pdf_dir_arg: Optional[Path] = None) -> Path:
    if pdf_dir_arg:
        console.print(f"\n[dim]-> using command line directory: {pdf_dir_arg}[/dim]")
        return pdf_dir_arg

    if not _is_interactive():
        raise typer.BadParameter("PDF directory must be provided in non-interactive mode.")

    console.print("\n" + "=" * 60)
    console.print("[bold cyan]Step 3: Input PDF Directory[/bold cyan]")
    console.print("=" * 60)

    while True:
        path = Path(Prompt.ask("PDF directory").strip().strip("\"'"))
        if not path.exists():
            console.print(f"[red]Path does not exist:[/red] {path}")
            continue
        if not path.is_dir():
            console.print(f"[red]Path is not a directory:[/red] {path}")
            continue
        return path


def _collect_pdf_files(pdf_dir: Path, recursive: bool) -> list[Path]:
    files = pdf_dir.rglob("*.pdf") if recursive else pdf_dir.glob("*.pdf")
    return [path for path in files if path.is_file()]


def _suggest_batch_size(file_count: int) -> int:
    if file_count <= 5:
        return file_count
    if file_count <= 20:
        return 5
    if file_count <= 50:
        return 8
    return 10


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        _print_welcome()
        console.print("Quick start:")
        console.print("  paperinsight check")
        console.print("  paperinsight config")
        console.print("  paperinsight analyze <pdf-dir>")
        console.print()
        console.print(ctx.get_help())


@app.command()
def analyze(
    pdf_dir: Optional[Path] = typer.Argument(None, help="Directory containing PDF files."),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Output directory."),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Recursively scan subdirectories."),
    max_pages: int = typer.Option(0, "--max-pages", help="Maximum pages per PDF. 0 means unlimited."),
    mode: str = typer.Option("auto", "--mode", "-m", help="Run mode: auto, api, regex."),
    no_cache: bool = typer.Option(False, "--no-cache", help="Disable cache."),
    export_json: bool = typer.Option(False, "--json", help="Also export JSON report."),
    bilingual: Optional[bool] = typer.Option(None, "--bilingual/--no-bilingual", help="Enable bilingual output."),
    rename_pdfs: Optional[bool] = typer.Option(None, "--rename-pdfs/--no-rename-pdfs", help="Rename PDFs after analysis."),
    skip_checks: bool = typer.Option(False, "--skip-checks", help="Skip startup checks."),
) -> None:
    _print_welcome()
    config = load_config()

    if not skip_checks and not _run_startup_checks(config):
        raise typer.Exit(1)
    if skip_checks:
        console.print("\n[yellow][!][/yellow] Startup checks skipped")

    config = load_config()
    selected_mode = _select_mode(config, mode)
    pdf_dir = _get_pdf_directory(pdf_dir)
    pdf_files = _collect_pdf_files(pdf_dir, recursive)

    if output_dir is None:
        output_dir = pdf_dir / "output"

    mineru_config = config.get("mineru", {})
    paddlex_config = config.get("paddlex", {"enabled": False, "token": ""})
    llm_config = config.get("llm", {})
    web_config = config.get("web_search", {})
    cache_config = config.get("cache", {})
    output_config = config.get("output", {})
    pdf_config = config.get("pdf", {})
    cleaner_config = config.get("cleaner", {})
    output_formats = list(output_config.get("format", ["excel"]))

    if export_json and "json" not in output_formats:
        output_formats.append("json")

    use_llm = selected_mode == "api" and llm_config.get("enabled", False)
    use_paddlex = selected_mode == "api" and paddlex_config.get("enabled", False)
    use_mineru_batch = (
        selected_mode == "api"
        and mineru_config.get("enabled", False)
        and mineru_config.get("mode") == "api"
        and len(pdf_files) > 1
    )
    batch_size = 1
    if use_mineru_batch:
        suggested_batch_size = min(_suggest_batch_size(len(pdf_files)), len(pdf_files))
        console.print(f"\nBatch MinerU processing available for {len(pdf_files)} PDFs.")
        console.print("Larger batch size is faster, but each batch takes longer to return.")
        batch_size = int(_prompt_or_default("Batch size", default=str(suggested_batch_size)))
        batch_size = max(1, min(batch_size, len(pdf_files)))

    if use_llm:
        try:
            provider = llm_config.get("provider", "")
            if provider == "openai":
                from paperinsight.llm.openai_client import OpenAIClient

                OpenAIClient(
                    api_key=llm_config["api_key"],
                    model=llm_config.get("model", "gpt-4o"),
                    base_url=llm_config.get("base_url") or None,
                    timeout=llm_config.get("timeout", 120),
                )
            elif provider == "deepseek":
                from paperinsight.llm.deepseek_client import DeepSeekClient

                DeepSeekClient(api_key=llm_config["api_key"], model=llm_config.get("model", "deepseek-chat"))
            elif provider == "wenxin":
                from paperinsight.llm.wenxin_client import WenxinClient

                wenxin = llm_config.get("wenxin", {})
                WenxinClient(
                    client_id=wenxin.get("client_id"),
                    client_secret=wenxin.get("client_secret"),
                    model=llm_config.get("model", "ernie-4.0-8k"),
                )
            elif provider == "longcat":
                from paperinsight.llm.longcat_client import LongcatClient

                longcat = llm_config.get("longcat", {})
                LongcatClient(
                    api_key=llm_config["api_key"],
                    model=longcat.get("model", llm_config.get("model", "LongCat-Flash-Chat")),
                    base_url=longcat.get("base_url", llm_config.get("base_url", "https://api.longcat.chat/openai")),
                    timeout=llm_config.get("timeout", 120),
                )
            console.print(f"\n[green][OK][/green] LLM enabled: {provider}")
        except Exception as exc:
            console.print(f"\n[red][X][/red] LLM init failed: {exc}")
            use_llm = False

    if rename_pdfs is None:
        rename_pdfs = output_config.get("rename_pdfs", False)

    if use_llm:
        if bilingual is None:
            bilingual = _confirm_or_default("Enable bilingual output?", default=output_config.get("bilingual_text", False))
        output_config["bilingual_text"] = bool(bilingual)
    else:
        output_config["bilingual_text"] = False

    console.print("\n" + "=" * 60)
    console.print("[bold cyan]Run Summary[/bold cyan]")
    console.print("=" * 60)
    console.print(f"  PDF dir:        {pdf_dir}")
    console.print(f"  Output dir:     {output_dir}")
    console.print(f"  PDF count:      {len(pdf_files)}")
    console.print(f"  Recursive:      {recursive}")
    console.print(f"  Mode:           {selected_mode}")
    console.print(f"  LLM:            {use_llm}")
    console.print(f"  PaddleX OCR:    {use_paddlex}")
    console.print(f"  MinerU batch:   {use_mineru_batch}")
    if use_mineru_batch:
        console.print(f"  Batch size:     {batch_size}")
    console.print(f"  Web search:     {bool(web_config.get('enabled'))}")
    console.print(f"  Cache:          {not no_cache}")
    console.print(f"  Bilingual:      {bool(output_config.get('bilingual_text'))}")
    console.print(f"  Rename PDFs:    {rename_pdfs}")
    console.print("=" * 60)

    if not _confirm_or_default("Start analysis?", default=True):
        console.print("[yellow]Cancelled[/yellow]")
        raise typer.Exit(0)

    full_config = {
        "llm": llm_config,
        "mineru": mineru_config,
        "paddlex": paddlex_config,
        "cleaner": cleaner_config,
        "pdf": pdf_config,
        "cache": cache_config,
        "web_search": web_config,
        "output": {**output_config, "format": output_formats},
    }

    pipeline = AnalysisPipeline(
        output_dir=output_dir,
        config=full_config,
        cache_dir=cache_config.get("directory", ".cache"),
    )

    progress_context = (
        Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console)
        if _is_interactive()
        else nullcontext()
    )

    with progress_context as progress:
        if progress is not None:
            progress.add_task("Running analysis...", total=None)
        stats = pipeline.run(
            pdf_dir=pdf_dir,
            recursive=recursive,
            max_pages=max_pages if max_pages > 0 else (pdf_config.get("max_pages") or None),
            use_cache=cache_config.get("enabled", True) and not no_cache,
            sort_by_if=output_config.get("sort_by_if", True),
            rename_pdfs=rename_pdfs,
            rename_template=output_config.get("rename_template"),
            pdf_files=pdf_files,
            batch_size=batch_size,
        )

    console.print()
    if stats["status"] == "completed":
        table = Table(title="Analysis Stats")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("PDF count", str(stats["pdf_count"]))
        table.add_row("Success", str(stats["success_count"]))
        table.add_row("Failed", str(stats["error_count"]))
        if "renamed_count" in stats:
            table.add_row("Renamed", str(stats["renamed_count"]))
        console.print(table)
        if stats.get("report_files"):
            console.print("\n[bold]Generated reports:[/bold]")
            for report_type, path in stats["report_files"].items():
                console.print(f"  - {report_type}: {path}")
    else:
        console.print("[red]No PDF files found[/red]")


@app.command()
def config() -> None:
    _print_welcome()
    console.print("\n[bold cyan]Config Wizard[/bold cyan]")
    console.print("-" * 60)
    wizard = ConfigWizard()
    wizard.run(force=True)


@app.command()
def version() -> None:
    console.print(f"PaperInsight CLI v{__version__}")


@app.command()
def doctor() -> None:
    _print_welcome()
    config = load_config()
    _run_startup_checks(config, allow_config_wizard=False)
    console.print("\n[bold cyan]Extra Diagnostics[/bold cyan]")
    console.print("-" * 60)
    try:
        import requests

        console.print("[cyan]Testing network...[/cyan]")
        requests.head("https://www.baidu.com", timeout=5)
        console.print("  [green][OK][/green] Network reachable")
    except Exception as exc:
        console.print(f"  [yellow][!][/yellow] Network check failed: {exc}")

    console.print("\n[bold]Recommended mode:[/bold]")
    console.print("  api" if _has_online_capability(config) else "  regex")


@app.command()
def check() -> None:
    _print_welcome()
    config = load_config()
    if not _run_startup_checks(config, allow_config_wizard=False):
        raise typer.Exit(1)


@app.command()
def cache_info() -> None:
    from paperinsight.core.cache import CacheManager

    stats = CacheManager().get_cache_stats()
    table = Table(title="Cache Stats")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Data cache files", str(stats["data_cache_count"]))
    table.add_row("OCR cache files", str(stats["ocr_cache_count"]))
    table.add_row("Total size", f"{stats['total_size_mb']} MB")
    console.print(table)


@app.command()
def clear_cache() -> None:
    from paperinsight.core.cache import CacheManager

    CacheManager().clear_cache()
    console.print("[green]Cache cleared[/green]")


@agent_app.command("prepare")
def agent_prepare(
    pdf_dir: Path = typer.Argument(..., help="Directory containing PDF files."),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Agent run root directory."),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Recursively scan subdirectories."),
    run_name: Optional[str] = typer.Option(None, "--run-name", help="Optional run directory name."),
    no_cache: bool = typer.Option(False, "--no-cache", help="Disable markdown cache reuse."),
) -> None:
    config = load_config()
    pdf_dir = pdf_dir.resolve()

    if not pdf_dir.exists():
        raise typer.BadParameter(f"Input directory does not exist: {pdf_dir}")
    if not pdf_dir.is_dir():
        raise typer.BadParameter(f"Input path is not a directory: {pdf_dir}")

    pdf_files = _collect_pdf_files(pdf_dir, recursive)
    if not pdf_files:
        console.print("[red]No PDF files found[/red]")
        raise typer.Exit(1)

    if output_dir is None:
        output_dir = pdf_dir / "agent_runs"

    cache_config = config.get("cache", {})
    pipeline = AgentPreparePipeline(
        output_dir=output_dir,
        config={
            "mineru": config.get("mineru", {}),
            "cache": cache_config,
        },
        cache_dir=cache_config.get("directory", ".cache"),
    )

    stats = pipeline.prepare(
        pdf_dir=pdf_dir,
        recursive=recursive,
        pdf_files=pdf_files,
        use_cache=cache_config.get("enabled", True) and not no_cache,
        run_name=run_name,
    )

    console.print()
    console.print("[bold cyan]Agent Prepare Complete[/bold cyan]")
    console.print(f"  PDFs:              {stats['pdf_count']}")
    console.print(f"  Prepared:          {stats['success_count']}")
    console.print(f"  Parse failed:      {stats['error_count']}")
    console.print(f"  Run dir:           {stats['run_dir']}")
    console.print(f"  Manifest:          {stats['manifest_path']}")
    console.print(f"  Identity jobs:     {stats['identity_jobs_path']}")
    console.print(f"  Identity results:  {stats['identity_results_path']}")
    console.print(f"  Prompt file:       {stats['identity_prompt_path']}")


@agent_app.command("import-identity")
def agent_import_identity(
    run_dir: Path = typer.Argument(..., help="Agent run directory."),
    results_path: Optional[Path] = typer.Option(None, "--results", help="Identity results JSONL path."),
) -> None:
    run_dir = run_dir.resolve()
    if not run_dir.exists():
        raise typer.BadParameter(f"Run directory does not exist: {run_dir}")
    if not run_dir.is_dir():
        raise typer.BadParameter(f"Run path is not a directory: {run_dir}")

    config = load_config()
    cache_config = config.get("cache", {})
    pipeline = AgentPreparePipeline(
        output_dir=run_dir.parent,
        config={"mineru": {"enabled": False}, "cache": cache_config},
        cache_dir=cache_config.get("directory", ".cache"),
    )
    stats = pipeline.import_identity_results(run_dir=run_dir, results_path=results_path)

    console.print()
    console.print("[bold cyan]Identity Import Complete[/bold cyan]")
    console.print(f"  Imported:          {stats['imported_count']}")
    console.print(f"  Invalid:           {stats['invalid_count']}")
    console.print(f"  Unmatched:         {stats['unmatched_count']}")
    console.print(f"  Manifest:          {stats['manifest_path']}")
    console.print(f"  Summary:           {stats['summary_path']}")


@agent_app.command("extract-metrics")
def agent_extract_metrics(
    run_dir: Path = typer.Argument(..., help="Agent run directory."),
    force: bool = typer.Option(False, "--force", help="Re-run metrics extraction even if outputs already exist."),
) -> None:
    run_dir = run_dir.resolve()
    if not run_dir.exists():
        raise typer.BadParameter(f"Run directory does not exist: {run_dir}")
    if not run_dir.is_dir():
        raise typer.BadParameter(f"Run path is not a directory: {run_dir}")

    config = load_config()
    cache_config = config.get("cache", {})
    pipeline = AgentPreparePipeline(
        output_dir=run_dir.parent,
        config={
            "mineru": {"enabled": False},
            "cache": cache_config,
            "llm": config.get("llm", {}),
            "cleaner": config.get("cleaner", {}),
            "output": config.get("output", {}),
        },
        cache_dir=cache_config.get("directory", ".cache"),
    )
    stats = pipeline.extract_metrics(run_dir=run_dir, force=force)

    console.print()
    console.print("[bold cyan]Metrics Extraction Complete[/bold cyan]")
    console.print(f"  Processed:         {stats['processed_count']}")
    console.print(f"  Failed:            {stats['failed_count']}")
    console.print(f"  Skipped:           {stats['skipped_count']}")
    console.print(f"  Manifest:          {stats['manifest_path']}")
    console.print(f"  Summary:           {stats['summary_path']}")


@agent_app.command("finalize")
def agent_finalize(
    run_dir: Path = typer.Argument(..., help="Agent run directory."),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Report output directory."),
    export_json: bool = typer.Option(False, "--json", help="Also export JSON report."),
) -> None:
    run_dir = run_dir.resolve()
    if not run_dir.exists():
        raise typer.BadParameter(f"Run directory does not exist: {run_dir}")
    if not run_dir.is_dir():
        raise typer.BadParameter(f"Run path is not a directory: {run_dir}")

    config = load_config()
    cache_config = config.get("cache", {})
    output_config = config.get("output", {})
    pipeline = AgentPreparePipeline(
        output_dir=run_dir.parent,
        config={"cache": cache_config, "output": output_config},
        cache_dir=cache_config.get("directory", ".cache"),
    )
    stats = pipeline.finalize(
        run_dir=run_dir,
        output_dir=output_dir,
        sort_by_if=output_config.get("sort_by_if", True),
        export_json=export_json,
    )

    console.print()
    console.print("[bold cyan]Agent Finalize Complete[/bold cyan]")
    console.print(f"  Finalized:         {stats['finalized_count']}")
    console.print(f"  Incomplete:        {stats['incomplete_count']}")
    console.print(f"  Manifest:          {stats['manifest_path']}")
    for report_type, path in stats["report_files"].items():
        console.print(f"  {report_type.title()} report:     {path}")
    console.print(f"  Summary:           {stats['summary_path']}")


if __name__ == "__main__":
    app()
