"""配置工具函数。"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any


def configure_logging(level: str = "INFO") -> None:
    """初始化基础日志配置。"""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(level=numeric_level)


def load_json_file(path: str | Path) -> Any:
    """加载 JSON 文件。"""
    file_path = Path(path).expanduser().resolve()
    with file_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_yaml_file(path: str | Path) -> dict[str, Any]:
    """加载 YAML 文件。

    当前优先使用 PyYAML；如果环境里没有安装，会给出明确错误。
    """
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Loading YAML config requires PyYAML to be installed") from exc

    file_path = Path(path).expanduser().resolve()
    with file_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a mapping at top level: {file_path}")

    return data
