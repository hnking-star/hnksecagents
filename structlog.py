"""structlog 的最小本地兼容层。

当前仓库还没完成完整依赖管理，为了让骨架代码在本地验证阶段可运行，
这里提供一个非常轻量的兼容实现。
"""

from __future__ import annotations

import logging
from typing import Any


class _CompatLogger:
    """兼容 structlog 常用接口的轻量日志对象。"""

    def __init__(self, name: str | None = None) -> None:
        """初始化日志对象。"""
        logging.basicConfig(level=logging.INFO)
        self._logger = logging.getLogger(name or "hnksecagents")

    def debug(self, event: str, **kwargs: Any) -> None:
        """输出 debug 日志。"""
        self._logger.debug("%s %s", event, kwargs if kwargs else "")

    def info(self, event: str, **kwargs: Any) -> None:
        """输出 info 日志。"""
        self._logger.info("%s %s", event, kwargs if kwargs else "")

    def warning(self, event: str, **kwargs: Any) -> None:
        """输出 warning 日志。"""
        self._logger.warning("%s %s", event, kwargs if kwargs else "")

    def error(self, event: str, **kwargs: Any) -> None:
        """输出 error 日志。"""
        self._logger.error("%s %s", event, kwargs if kwargs else "")

    def exception(self, event: str, **kwargs: Any) -> None:
        """输出 exception 日志。"""
        self._logger.exception("%s %s", event, kwargs if kwargs else "")


def get_logger(name: str | None = None) -> _CompatLogger:
    """返回兼容 structlog.get_logger() 的日志对象。"""
    return _CompatLogger(name)
