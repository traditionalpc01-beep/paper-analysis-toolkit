"""
配置读写与兼容处理。
"""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import yaml

from paperinsight.utils.config_crypto import (
    decrypt_sensitive_fields,
    encrypt_sensitive_fields,
)

DEFAULT_CONFIG: dict[str, Any] = {
    "paddlex": {
        "enabled": False,
        "token": "",
        "model": "PaddleOCR-VL-1.5",
        "use_doc_orientation": False,
        "use_doc_unwarping": False,
        "use_layout_detection": True,
        "use_chart_recognition": False,
        "timeout": 300,
        "poll_interval": 5,
    },
    "llm": {
        "enabled": False,
        "provider": "openai",
        "api_key": "",
        "model": "gpt-4o",
        "base_url": "",
        "timeout": 120,
    },
    "web_search": {
        "enabled": True,
        "timeout": 30,
    },
    "cache": {
        "enabled": True,
        "directory": ".cache",
    },
    "output": {
        "format": ["excel"],
        "sort_by_if": True,
        "generate_error_log": True,
        "rename_pdfs": False,
        "rename_template": "[{year}_{impact_factor}_{journal}]_{title}.pdf",
    },
    "pdf": {
        "max_pages": 0,
        "text_ratio_threshold": 0.1,
    },
}


def get_config_path() -> Path:
    """返回用户配置文件路径。"""
    config_dir = Path.home() / ".paperinsight"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.yaml"


def normalize_config(config: dict[str, Any] | None) -> dict[str, Any]:
    """将旧版扁平配置统一转换为当前嵌套结构。"""
    normalized = copy.deepcopy(DEFAULT_CONFIG)
    if not config:
        return normalized

    config = decrypt_sensitive_fields(copy.deepcopy(config))

    if any(key in config for key in DEFAULT_CONFIG):
        _deep_merge(normalized, config)

    if "use_paddlex" in config:
        normalized["paddlex"]["enabled"] = bool(config.get("use_paddlex"))
    if "paddlex_token" in config:
        normalized["paddlex"]["token"] = config.get("paddlex_token", "")

    if "use_llm" in config:
        normalized["llm"]["enabled"] = bool(config.get("use_llm"))
    if "llm_provider" in config:
        normalized["llm"]["provider"] = config.get("llm_provider", "openai")
    if "llm_api_key" in config:
        normalized["llm"]["api_key"] = config.get("llm_api_key", "")
    if "llm_model" in config:
        normalized["llm"]["model"] = config.get("llm_model", "gpt-4o")
    if "llm_base_url" in config:
        normalized["llm"]["base_url"] = config.get("llm_base_url", "")

    if "use_web_search" in config:
        normalized["web_search"]["enabled"] = bool(config.get("use_web_search"))

    if "enable_cache" in config:
        normalized["cache"]["enabled"] = bool(config.get("enable_cache"))
    if "cache_dir" in config:
        normalized["cache"]["directory"] = config.get("cache_dir", ".cache")

    if "output_formats" in config and isinstance(config["output_formats"], list):
        normalized["output"]["format"] = config["output_formats"]
    if "sort_by_if" in config:
        normalized["output"]["sort_by_if"] = bool(config.get("sort_by_if"))
    if "rename_pdfs" in config:
        normalized["output"]["rename_pdfs"] = bool(config.get("rename_pdfs"))
    if "rename_template" in config:
        normalized["output"]["rename_template"] = config.get(
            "rename_template",
            normalized["output"]["rename_template"],
        )

    if "max_pages" in config:
        normalized["pdf"]["max_pages"] = int(config.get("max_pages") or 0)
    if "text_ratio_threshold" in config:
        normalized["pdf"]["text_ratio_threshold"] = float(
            config.get("text_ratio_threshold") or normalized["pdf"]["text_ratio_threshold"]
        )

    normalized["output"]["format"] = _normalize_output_formats(normalized["output"]["format"])
    return normalized


def load_config() -> dict[str, Any]:
    """加载并标准化配置。"""
    config_path = get_config_path()
    if not config_path.exists():
        return copy.deepcopy(DEFAULT_CONFIG)

    with config_path.open("r", encoding="utf-8") as file:
        raw_config = yaml.safe_load(file) or {}

    return normalize_config(raw_config)


def save_config(config: dict[str, Any]) -> Path:
    """保存标准化后的配置。"""
    config_path = get_config_path()
    normalized = normalize_config(config)
    encrypted_config = encrypt_sensitive_fields(normalized)

    with config_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(encrypted_config, file, default_flow_style=False, allow_unicode=True)

    os.chmod(config_path, 0o600)
    return config_path


def _deep_merge(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value


def _normalize_output_formats(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]

    formats = []
    for item in value or []:
        text = str(item).strip().lower()
        if text and text not in formats:
            formats.append(text)

    return formats or ["excel"]
