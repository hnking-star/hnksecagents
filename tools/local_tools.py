"""本地工具自动生成模块。"""

from importlib import import_module

def add_numbers(*args, **kwargs):
    """计算两个数字的和"""
    module = import_module("hnk_agent.tooling.builtins.simple_tools")
    implementation = getattr(module, "add_numbers")
    return implementation(*args, **kwargs)

def echo_text(*args, **kwargs):
    """原样返回输入文本"""
    module = import_module("hnk_agent.tooling.builtins.simple_tools")
    implementation = getattr(module, "echo_text")
    return implementation(*args, **kwargs)

__all__ = ["add_numbers", "echo_text"]
