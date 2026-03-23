"""工具定义模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolSpec:
    """工具元数据定义。"""

    name: str
    description: str = ""
    module_name: str = ""
    callable_name: str = ""
    source_module: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
