"""langchain_core.tools 的最小本地兼容层。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class BaseTool:
    """最小工具对象。"""

    name: str
    description: str = ""
    coroutine: Callable[..., Awaitable[Any]] | None = None

    async def ainvoke(self, input_data: Any) -> Any:
        """异步调用工具。"""
        if self.coroutine is None:
            raise RuntimeError(f"Tool '{self.name}' does not have an async coroutine")

        if isinstance(input_data, dict):
            return await self.coroutine(**input_data)
        return await self.coroutine(input_data)


class StructuredTool(BaseTool):
    """兼容 StructuredTool.from_function 的最小实现。"""

    @classmethod
    def from_function(
        cls,
        *,
        name: str,
        description: str,
        coroutine: Callable[..., Awaitable[Any]],
    ) -> "StructuredTool":
        """通过异步函数创建工具对象。"""
        return cls(name=name, description=description, coroutine=coroutine)


def tool(func: Callable[..., Awaitable[Any]]) -> BaseTool:
    """把异步函数包装成最小 BaseTool。"""
    description = func.__doc__ or ""
    return BaseTool(name=func.__name__, description=description, coroutine=func)
