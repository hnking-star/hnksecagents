"""内建工具导出与注册入口。"""

from hnk_agent.tooling.registry import ToolRegistry
from hnk_agent.tooling.spec import ToolSpec
from hnk_agent.tooling.builtins.simple_tools import add_numbers, echo_text

__all__ = [
    "add_numbers",
    "echo_text",
    "register_builtin_tools",
]


def register_builtin_tools(registry: ToolRegistry) -> None:
    """把当前最小内建工具注册进工具中心。"""
    registry.register_callable(
        "add_numbers",
        add_numbers,
        description="计算两个数字的和",
        module_name="local_tools",
    )
    registry.register_callable(
        "echo_text",
        echo_text,
        description="原样返回输入文本",
        module_name="local_tools",
    )
