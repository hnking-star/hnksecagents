"""最小内建工具集合。"""

from __future__ import annotations


def add_numbers(left: int | float, right: int | float) -> int | float:
    """返回两个数字的和。"""
    return left + right


def echo_text(text: str) -> str:
    """原样返回输入文本。"""
    return text
