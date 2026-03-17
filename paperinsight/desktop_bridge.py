from __future__ import annotations

import argparse
import copy
import json
import logging
import os
import socket
import subprocess
import sys
import time
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
    llm_config = config.get("llm", {})
    llm_enabled = bool(llm_config.get("enabled", False))
    llm_provider = str(llm_config.get("provider", "deepseek")).lower()
    llm_api_key = str(llm_config.get("api_key", "")).strip()
    wenxin_config = llm_config.get("wenxin", {})
    has_llm_credentials = False
    if llm_enabled:
        if llm_provider == "wenxin":
            has_llm_credentials = bool(
                str(wenxin_config.get("client_id", "")).strip()
                and str(wenxin_config.get("client_secret", "")).strip()
            )
        else:
            has_llm_credentials = bool(llm_api_key)

    mineru_config = config.get("mineru", {})
    has_mineru_api = bool(
        mineru_config.get("enabled", False)
        and mineru_config.get("mode") == "api"
        and str(mineru_config.get("token", "")).strip()
    )
    paddlex_config = config.get("paddlex", {})
    has_paddlex = bool(
        paddlex_config.get("enabled", False) and str(paddlex_config.get("token", "")).strip()
    )
    return any(
        [
            has_mineru_api,
            has_paddlex,
            has_llm_credentials,
        ]
    )


def _preferred_python_command(config: dict[str, Any]) -> str:
    engine = config.get("desktop", {}).get("engine", {})
    configured = str(engine.get("python_path", "")).strip()
    if configured:
        return configured
    if os.environ.get("PAPERINSIGHT_PYTHON"):
        return os.environ["PAPERINSIGHT_PYTHON"]
    return "python" if sys.platform == "win32" else "python3"


def _probe_network() -> dict[str, Any]:
    targets = [
        ("www.baidu.com", 443),
        ("www.bing.com", 443),
    ]
    last_error = "未执行网络检测"
    for host, port in targets:
        started = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=2.5):
                latency_ms = round((time.perf_counter() - started) * 1000)
                return {
                    "available": True,
                    "target": f"{host}:{port}",
                    "latencyMs": latency_ms,
                    "message": f"已连接 {host}:{port}，基础联网可用。",
                }
        except OSError as error:
            last_error = str(error)
    return {
        "available": False,
        "target": "",
        "latencyMs": None,
        "message": f"基础联网检测失败：{last_error}",
    }


def _probe_system_python(config: dict[str, Any]) -> dict[str, Any]:
    command = _preferred_python_command(config)
    probe_code = (
        "import importlib.util, json, platform, sys; "
        "spec = importlib.util.find_spec('paperinsight.desktop_bridge'); "
        "print(json.dumps({"
        "'executable': sys.executable, "
        "'version': platform.python_version(), "
        "'hasPaperInsight': spec is not None"
        "}, ensure_ascii=False))"
    )
    try:
        result = subprocess.run(
            [command, "-c", probe_code],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except FileNotFoundError:
        return {
            "available": False,
            "command": command,
            "executable": "",
            "version": "",
            "hasPaperInsight": False,
            "message": f"未找到 Python 命令：{command}",
        }
    except Exception as error:
        return {
            "available": False,
            "command": command,
            "executable": "",
            "version": "",
            "hasPaperInsight": False,
            "message": f"Python 检测失败：{error}",
        }

    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or f"退出码 {result.returncode}"
        return {
            "available": False,
            "command": command,
            "executable": "",
            "version": "",
            "hasPaperInsight": False,
            "message": f"Python 不可用：{message}",
        }

    try:
        payload = json.loads((result.stdout or "").strip().splitlines()[-1])
    except Exception:
        payload = {}

    has_paperinsight = bool(payload.get("hasPaperInsight"))
    version = str(payload.get("version", ""))
    executable = str(payload.get("executable", ""))
    message = "已检测到可用的系统 Python 环境。"
    if not has_paperinsight:
        message = "系统 Python 可用，但该环境未安装 paperinsight。"

    return {
        "available": True,
        "command": command,
        "executable": executable,
        "version": version,
        "hasPaperInsight": has_paperinsight,
        "message": message,
    }


def _build_startup_recommendation(
    config: dict[str, Any],
    checks: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    bundled = checks["bundledBackend"]
    network = checks["network"]
    system_python = checks["systemPython"]

    if bundled.get("available"):
        engine_mode = "bundled"
        engine_reason = "检测到内置后端，可直接启动，无需依赖用户本地 Python 环境。"
        fallback_engine = (
            {
                "mode": "system_python",
                "label": "系统 Python",
                "reason": "如果需要沿用本地脚本环境，可切换到系统 Python。",
            }
            if system_python.get("available") and system_python.get("hasPaperInsight")
            else None
        )
    elif system_python.get("available") and system_python.get("hasPaperInsight"):
        engine_mode = "system_python"
        engine_reason = "未检测到内置后端，但系统 Python 环境完整，可作为默认启动方式。"
        fallback_engine = None
    else:
        engine_mode = "manual_check"
        engine_reason = "暂未检测到可直接使用的运行引擎，请检查内置后端或系统 Python 环境。"
        fallback_engine = None

    if network.get("available") and _has_online_capability(config):
        analysis_mode = "api"
        analysis_reason = "网络可用且检测到完整 API 凭据，推荐优先使用智能 API 模式。"
    elif network.get("available"):
        analysis_mode = "regex"
        analysis_reason = "网络可用，但尚未检测到完整 API 凭据，建议先用正则兜底。"
    else:
        analysis_mode = "regex"
        analysis_reason = "当前网络不可用或受限，建议先用正则兜底。"

    fallback_tool = {
        "id": "regex",
        "label": "正则兜底",
        "reason": "当 API 或网络不可用时，仍可继续完成基础信息抽取。",
    }
    if engine_mode == "manual_check":
        fallback_tool = {
            "id": "manual_check",
            "label": "检查 Python/内置后端",
            "reason": "需要先修复启动引擎，再决定是否使用正则或 API 模式。",
        }

    if engine_mode == "manual_check":
        readiness = {
            "status": "blocked",
            "summary": "启动引擎不可用，需要先修复环境。",
        }
    elif analysis_mode == "regex":
        readiness = {
            "status": "limited",
            "summary": "软件可启动，建议先使用兜底模式运行。",
        }
    else:
        readiness = {
            "status": "ready",
            "summary": "基础环境检查通过，可按推荐方式启动。",
        }

    recommendation = {
        "engineMode": engine_mode,
        "engineLabel": {
            "bundled": "内置后端",
            "system_python": "系统 Python",
            "manual_check": "需手动检查",
        }.get(engine_mode, engine_mode),
        "engineReason": engine_reason,
        "analysisMode": analysis_mode,
        "analysisLabel": {"api": "智能 API", "regex": "正则兜底"}.get(analysis_mode, analysis_mode),
        "analysisReason": analysis_reason,
        "fallbackEngine": fallback_engine,
        "fallbackTool": fallback_tool,
    }
    return recommendation, readiness


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
    payload = _read_json_stdin()
    config = payload.get("config")
    if not isinstance(config, dict):
        config = load_config()
    desktop_engine = config.get("desktop", {}).get("engine", {})
    runtime = payload.get("runtime", {}) if isinstance(payload, dict) else {}
    bundled_available = bool(runtime.get("bundledAvailable", getattr(sys, "frozen", False)))
    bundled_path = runtime.get("bundledPath") or (sys.executable if getattr(sys, "frozen", False) else "")
    checks = {
        "bundledBackend": {
            "available": bundled_available,
            "current": bool(getattr(sys, "frozen", False)),
            "path": bundled_path,
            "message": (
                "已检测到内置后端。"
                if bundled_available
                else "当前未检测到内置后端，可改用系统 Python。"
            ),
        },
        "network": _probe_network(),
        "systemPython": _probe_system_python(config),
    }
    recommendation, readiness = _build_startup_recommendation(config, checks)
    _emit(
        {
            "ok": True,
            "env": {
                "pythonExecutable": sys.executable,
                "pythonVersion": sys.version,
                "platform": sys.platform,
                "version": __version__,
                "engineMode": desktop_engine.get("mode", "bundled"),
                "checks": checks,
                "recommendation": recommendation,
                "readiness": readiness,
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
