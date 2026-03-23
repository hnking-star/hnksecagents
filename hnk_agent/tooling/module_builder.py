"""本地工具模块生成器。"""

from __future__ import annotations

import keyword
import re
from pathlib import Path

from hnk_agent.tooling.registry import ToolRegistry
from hnk_agent.tooling.spec import ToolSpec


def _sanitize_python_name(name: str, *, fallback: str = "tool") -> str:
    """把任意名称转换成合法的 Python 标识符。"""
    candidate = re.sub(r"\W+", "_", name).strip("_")
    if not candidate:
        candidate = fallback
    if candidate[0].isdigit():
        candidate = f"tool_{candidate}"
    if keyword.iskeyword(candidate):
        candidate = f"{candidate}_tool"
    return candidate


class ToolModuleBuilder:
    """把 ToolRegistry 生成为可 import 的本地 tools 包。"""

    def __init__(self, package_name: str = "tools") -> None:
        """初始化模块生成器。"""
        self.package_name = package_name

    def build_package(self, registry: ToolRegistry, target_dir: str | Path) -> list[Path]:
        """把当前注册中心生成到目标目录。"""
        target_path = Path(target_dir).expanduser().resolve()
        target_path.mkdir(parents=True, exist_ok=True)

        written_files: list[Path] = []
        init_path = target_path / "__init__.py"
        init_path.write_text('"""本地工具自动生成包。"""\n', encoding="utf-8")
        written_files.append(init_path)

        modules: dict[str, list[ToolSpec]] = {}
        for spec in registry.get_all():
            module_name = _sanitize_python_name(spec.module_name or "local_tools", fallback="local_tools")
            modules.setdefault(module_name, []).append(spec)

        for module_name, specs in modules.items():
            module_path = target_path / f"{module_name}.py"
            module_path.write_text(
                self._render_module(module_name=module_name, specs=specs),
                encoding="utf-8",
            )
            written_files.append(module_path)

        return written_files

    def _render_module(self, module_name: str, specs: list[ToolSpec]) -> str:
        """渲染单个工具模块源码。"""
        lines: list[str] = [
            '"""本地工具自动生成模块。"""',
            "",
            "from importlib import import_module",
            "",
        ]

        export_names: list[str] = []
        for spec in specs:
            lines.extend(self._render_tool(spec))
            lines.append("")
            export_names.append(_sanitize_python_name(spec.name))

        if export_names:
            exports = ", ".join(f'"{name}"' for name in export_names)
            lines.append(f"__all__ = [{exports}]")
        else:
            lines.append("__all__ = []")

        return "\n".join(lines) + "\n"

    def _render_tool(self, spec: ToolSpec) -> list[str]:
        """渲染单个工具函数源码。"""
        function_name = _sanitize_python_name(spec.name)
        source_module = spec.source_module or str(spec.metadata.get("source_module", ""))
        callable_name = spec.callable_name or function_name

        if not source_module:
            raise ValueError(f"Tool '{spec.name}' is missing source_module")

        doc = spec.description or f"代理到 {source_module}.{callable_name}"

        return [
            f"def {function_name}(*args, **kwargs):",
            f'    """{doc}"""',
            f'    module = import_module("{source_module}")',
            f'    implementation = getattr(module, "{callable_name}")',
            "    return implementation(*args, **kwargs)",
        ]
