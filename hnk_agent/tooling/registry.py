"""工具注册中心。"""

from __future__ import annotations

from typing import Any

from hnk_agent.tooling.spec import ToolSpec


class ToolRegistry:
    """本地工具注册中心。

    这一版先提供最小能力：
    - 注册工具定义
    - 查询工具定义
    - 清空注册中心
    """

    def __init__(self) -> None:
        """初始化工具注册中心。"""
        self._tools: dict[str, ToolSpec] = {}
        self._implementations: dict[str, Any] = {}

    def register(self, spec: ToolSpec, implementation: Any | None = None) -> None:
        """注册一个工具定义。"""
        if implementation is not None:
            if not spec.callable_name and hasattr(implementation, "__name__"):
                spec.callable_name = str(implementation.__name__)
            if not spec.source_module and hasattr(implementation, "__module__"):
                spec.source_module = str(implementation.__module__)

        self._tools[spec.name] = spec
        if implementation is not None:
            self._implementations[spec.name] = implementation

    def register_callable(
        self,
        name: str,
        implementation: Any,
        *,
        description: str = "",
        module_name: str = "",
        callable_name: str = "",
        source_module: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """使用可调用对象快速注册工具。"""
        spec = ToolSpec(
            name=name,
            description=description,
            module_name=module_name,
            callable_name=callable_name,
            source_module=source_module,
            metadata=metadata or {},
        )
        self.register(spec, implementation=implementation)

    def get(self, name: str) -> ToolSpec | None:
        """获取指定工具定义。"""
        return self._tools.get(name)

    def get_implementation(self, name: str) -> Any | None:
        """获取指定工具实现。"""
        return self._implementations.get(name)

    def get_all(self) -> list[ToolSpec]:
        """返回所有已注册工具定义。"""
        return list(self._tools.values())

    def as_summary(self) -> str:
        """以简要文本形式返回已注册工具。"""
        if not self._tools:
            return "当前没有注册任何本地工具。"
        return "\n".join(
            f"- {tool.name}: {tool.description}".rstrip(": ")
            for tool in self._tools.values()
        )

    def has(self, name: str) -> bool:
        """判断某个工具是否已注册。"""
        return name in self._tools

    def clear(self) -> None:
        """清空注册中心。"""
        self._tools.clear()
        self._implementations.clear()
