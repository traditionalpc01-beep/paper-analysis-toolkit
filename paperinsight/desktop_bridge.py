from __future__ import annotations

import argparse
import copy
import json
import logging
import sys
from pathlib import Path
from typing import Any

from paperinsight import __version__
from paperinsight.core.pipeline import AnalysisPipeline
from paperinsight.utils.config import get_config_path, load_config, save_config


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _read_json_stdin() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    return json.loads(raw)


def _configure_logging() -> None:
    formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    for name in (
        "paperinsight",
        "paperinsight.pipeline",
        "paperinsight.extractor",
        "paperinsight.parser",
    ):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = False
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)


def _has_online_capability(config: dict[str, Any]) -> bool:
    return any(
        [
            config.get("mineru", {}).get("enabled", False)
            and config.get("mineru", {}).get("mode") == "api",
            config.get("paddlex", {}).get("enabled", False),
            config.get("llm", {}).get("enabled", False),
        ]
    )


def _collect_pdf_files(pdf_dir: Path, recursive: bool) -> list[Path]:
    pattern = "*.pdf"
    files = pdf_dir.rglob(pattern) if recursive else pdf_dir.glob(pattern)
    return sorted(path for path in files if path.is_file())


def _build_runtime_config(config: dict[str, Any], request: dict[str, Any]) -> tuple[dict[str, Any], str]:
    runtime_config = copy.deepcopy(config)
    requested_mode = str(request.get("mode") or "auto").lower()
    selected_mode = requested_mode
    if selected_mode == "auto":
        selected_mode = "api" if _has_online_capability(runtime_config) else "regex"

    if selected_mode == "regex":
        runtime_config.setdefault("llm", {})["enabled"] = False
        runtime_config.setdefault("paddlex", {})["enabled"] = False

    output_config = runtime_config.setdefault("output", {})
    formats = list(output_config.get("format", ["excel"]))
    if "excel" not in formats:
        formats.insert(0, "excel")
    if request.get("exportJson") and "json" not in formats:
        formats.append("json")
    if not request.get("exportJson"):
        formats = [item for item in formats if item != "json"] or ["excel"]
    output_config["format"] = formats

    if "renamePdfs" in request:
        output_config["rename_pdfs"] = bool(request.get("renamePdfs"))
    if "bilingual" in request and request.get("bilingual") is not None:
        output_config["bilingual_text"] = bool(request.get("bilingual"))

    cache_config = runtime_config.setdefault("cache", {})
    cache_config["enabled"] = bool(cache_config.get("enabled", True)) and not bool(request.get("noCache"))

    desktop_config = runtime_config.setdefault("desktop", {})
    ui_config = desktop_config.setdefault("ui", {})
    if request.get("pdfDir"):
        ui_config["last_pdf_dir"] = str(request["pdfDir"])
    if request.get("outputDir"):
        ui_config["last_output_dir"] = str(request["outputDir"])

    return runtime_config, selected_mode


def _build_stats(
    pdf_files: list[Path],
    results: list[Any],
    errors: list[dict[str, Any]],
    report_files: dict[str, str],
    renamed_count: int,
    processed_items: list[tuple[Path, Any]],
) -> dict[str, Any]:
    success_items = []
    for pdf_path, paper_data in processed_items:
        paper_info = paper_data.paper_info
        best_device = paper_data.get_best_device()
        success_items.append(
            {
                "file": pdf_path.name,
                "path": str(pdf_path),
                "title": paper_info.title,
                "journal": paper_info.journal_name,
                "impactFactor": paper_info.impact_factor,
                "bestEqe": best_device.eqe if best_device else None,
            }
        )

    error_items = [
        {
            "file": error.get("pdf_name", ""),
            "path": error.get("pdf_path", ""),
            "message": error.get("error_message", ""),
            "context": error.get("context", ""),
            "type": error.get("error_type", ""),
        }
        for error in errors
    ]

    return {
        "status": "completed",
        "pdfCount": len(pdf_files),
        "successCount": len(results),
        "errorCount": len(errors),
        "renamedCount": renamed_count,
        "reportFiles": report_files,
        "successItems": success_items,
        "errorItems": error_items,
    }


def command_config_get() -> int:
    config = load_config()
    _emit(
        {
            "ok": True,
            "config": config,
            "meta": {
                "version": __version__,
                "configPath": str(get_config_path()),
                "pythonExecutable": sys.executable,
            },
        }
    )
    return 0


def command_config_save() -> int:
    payload = _read_json_stdin()
    config = payload.get("config")
    if not isinstance(config, dict):
        _emit({"ok": False, "message": "缺少有效的 config 对象"})
        return 1

    path = save_config(config)
    _emit({"ok": True, "config": load_config(), "meta": {"configPath": str(path)}})
    return 0


def command_env_info() -> int:
    config = load_config()
    desktop_engine = config.get("desktop", {}).get("engine", {})
    _emit(
        {
            "ok": True,
            "env": {
                "pythonExecutable": sys.executable,
                "pythonVersion": sys.version,
                "platform": sys.platform,
                "version": __version__,
                "engineMode": desktop_engine.get("mode", "bundled"),
            },
        }
    )
    return 0


def command_analyze() -> int:
    _configure_logging()
    request = _read_json_stdin()
    config = load_config()
    runtime_config, selected_mode = _build_runtime_config(config, request)

    pdf_dir = Path(request.get("pdfDir") or "")
    if not str(pdf_dir):
        _emit({"type": "failed", "message": "请选择包含 PDF 的目录。"})
        return 1
    if not pdf_dir.exists() or not pdf_dir.is_dir():
        _emit({"type": "failed", "message": f"目录不存在: {pdf_dir}"})
        return 1

    output_dir = Path(request.get("outputDir") or (pdf_dir / "输出结果"))
    recursive = bool(request.get("recursive"))
    pdf_files = _collect_pdf_files(pdf_dir, recursive)

    if not pdf_files:
        _emit(
            {
                "type": "completed",
                "selectedMode": selected_mode,
                "stats": {
                    "status": "no_files",
                    "pdfCount": 0,
                    "successCount": 0,
                    "errorCount": 0,
                    "renamedCount": 0,
                    "reportFiles": {},
                    "successItems": [],
                    "errorItems": [],
                },
            }
        )
        return 0

    if runtime_config.get("desktop", {}).get("ui", {}).get("remember_last_paths", True):
        persisted_config = copy.deepcopy(config)
        persisted_config.setdefault("desktop", {}).setdefault("ui", {})
        persisted_config["desktop"]["ui"]["last_pdf_dir"] = runtime_config["desktop"]["ui"].get(
            "last_pdf_dir", ""
        )
        persisted_config["desktop"]["ui"]["last_output_dir"] = runtime_config["desktop"]["ui"].get(
            "last_output_dir", ""
        )
        save_config(persisted_config)

    output_dir.mkdir(parents=True, exist_ok=True)
    pipeline = AnalysisPipeline(
        output_dir=output_dir,
        config=runtime_config,
        cache_dir=runtime_config.get("cache", {}).get("directory", ".cache"),
    )

    results: list[Any] = []
    errors: list[dict[str, Any]] = []
    processed_items: list[tuple[Path, Any]] = []

    _emit(
        {
            "type": "started",
            "selectedMode": selected_mode,
            "total": len(pdf_files),
            "pdfDir": str(pdf_dir),
            "outputDir": str(output_dir),
        }
    )

    for index, pdf_path in enumerate(pdf_files, start=1):
        _emit(
            {
                "type": "progress",
                "stage": "processing",
                "currentFile": pdf_path.name,
                "currentPath": str(pdf_path),
                "completed": index - 1,
                "total": len(pdf_files),
            }
        )
        paper_data, error_info = pipeline.process_pdf(
            pdf_path=pdf_path,
            max_pages=request.get("maxPages") or None,
            use_cache=runtime_config.get("cache", {}).get("enabled", True),
        )
        pipeline._collect_batch_item_result(
            pdf_path=pdf_path,
            paper_data=paper_data,
            error_info=error_info,
            results=results,
            errors=errors,
            processed_items=processed_items,
        )

        if paper_data:
            paper_info = paper_data.paper_info
            _emit(
                {
                    "type": "file-complete",
                    "status": "success",
                    "completed": index,
                    "total": len(pdf_files),
                    "file": pdf_path.name,
                    "title": paper_info.title,
                    "journal": paper_info.journal_name,
                    "impactFactor": paper_info.impact_factor,
                }
            )
        else:
            _emit(
                {
                    "type": "file-complete",
                    "status": "error",
                    "completed": index,
                    "total": len(pdf_files),
                    "file": pdf_path.name,
                    "message": (error_info or {}).get("error_message", "处理失败"),
                }
            )

    renamed_count = 0
    if runtime_config.get("output", {}).get("rename_pdfs") and processed_items:
        renamed_count = pipeline._rename_pdfs(
            processed_items,
            runtime_config.get("output", {}).get(
                "rename_template", "[{year}_{impact_factor}_{journal}]_{title}.pdf"
            ),
        )

    report_files = pipeline._generate_reports(
        processed_items,
        errors,
        runtime_config.get("output", {}).get("sort_by_if", True),
    )

    if pipeline.error_logger.errors:
        error_log_path = pipeline.error_logger.save()
        if error_log_path:
            report_files["error_log"] = str(error_log_path)

    stats = _build_stats(pdf_files, results, errors, report_files, renamed_count, processed_items)
    _emit({"type": "completed", "selectedMode": selected_mode, "stats": stats})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PaperInsight desktop bridge")
    parser.add_argument(
        "command",
        choices=["config-get", "config-save", "env-info", "analyze"],
        help="Bridge command to execute",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "config-get":
            return command_config_get()
        if args.command == "config-save":
            return command_config_save()
        if args.command == "env-info":
            return command_env_info()
        if args.command == "analyze":
            return command_analyze()
        parser.error("Unknown command")
        return 2
    except Exception as exc:
        _emit({"ok": False, "type": "failed", "message": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
