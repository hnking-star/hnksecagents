"""安全工具 MCP 客户端封装。

通过 langchain-mcp-adapters 将外部 MCP Server（Nmap、Nuclei、SQLMap 等）
的工具转换为 LangChain BaseTool，自动注入到 agent.py 的工具列表。

快速启用方式：
1. 在 mcp_config.json 中将对应 server 的 "enabled" 改为 true
2. 确保宿主机已安装对应命令行工具（nmap / nuclei / sqlmap / ffuf 等）
3. 重启 langgraph dev

MCP 连接为惰性初始化：仅在 agent 实际构建时连接，连接失败的 server 会被跳过（打印警告），
不会阻断整个 agent 启动。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# mcp_config.json 默认放在项目根目录
_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "mcp_config.json"


def _load_config(config_path: Path | str | None = None) -> dict[str, Any]:
    """加载 MCP 配置文件，返回 mcpServers 字典（仅 enabled=true 的条目）。"""
    path = Path(config_path or os.environ.get("MCP_CONFIG_PATH", str(_DEFAULT_CONFIG_PATH)))
    if not path.exists():
        logger.debug("mcp_config_not_found", path=str(path))
        return {}

    with path.open() as f:
        raw = json.load(f)

    servers: dict[str, Any] = raw.get("mcpServers", {})
    enabled = {
        name: cfg
        for name, cfg in servers.items()
        if cfg.get("enabled", True) and not name.startswith("_")
    }
    logger.info(
        "mcp_config_loaded",
        total=len(servers),
        enabled=len(enabled),
        names=list(enabled.keys()),
        path=str(path),
    )
    return enabled


def _resolve_env(value: str) -> str:
    """将 ${VAR} 形式替换为环境变量实际值（找不到时保留原始占位符）。"""
    def replace(m: re.Match) -> str:  # type: ignore[type-arg]
        var = m.group(1)
        return os.environ.get(var, m.group(0))

    return re.sub(r"\$\{([^}]+)\}", replace, value)


def _build_client_config(servers: dict[str, Any]) -> dict[str, Any]:
    """将 mcp_config.json 格式转为 MultiServerMCPClient 所需格式。

    MultiServerMCPClient 期望：
    {
      "server_name": {
        "transport": "stdio",          # or "sse"
        "command": "npx",
        "args": [...],
        "env": {...}
      }
    }
    """
    client_cfg: dict[str, Any] = {}
    for name, cfg in servers.items():
        transport = cfg.get("transport", "stdio")
        entry: dict[str, Any] = {"transport": transport}

        if transport == "stdio":
            entry["command"] = cfg.get("command", "")
            entry["args"] = cfg.get("args", [])
            raw_env: dict[str, str] = cfg.get("env", {})
            entry["env"] = {k: _resolve_env(v) for k, v in raw_env.items()}
        elif transport == "sse":
            entry["url"] = _resolve_env(cfg.get("url", ""))
            raw_headers: dict[str, str] = cfg.get("headers", {})
            entry["headers"] = {k: _resolve_env(v) for k, v in raw_headers.items()}

        client_cfg[name] = entry
    return client_cfg


async def load_mcp_tools(config_path: Path | str | None = None) -> list[Any]:
    """异步加载所有已启用 MCP server 的工具列表。

    - 连接失败的 server 会跳过（只打印 warning），不抛出异常
    - 返回 LangChain BaseTool 列表，可直接追加到 agent tools

    使用示例（在 async 上下文中）::

        tools = await load_mcp_tools()
    """
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError:
        logger.warning(
            "langchain_mcp_adapters_not_installed",
            hint="run: uv add langchain-mcp-adapters",
        )
        return []

    enabled_servers = _load_config(config_path)
    if not enabled_servers:
        logger.debug("no_mcp_servers_enabled")
        return []

    client_cfg = _build_client_config(enabled_servers)
    all_tools: list[Any] = []

    async with MultiServerMCPClient(client_cfg) as client:
        for server_name in client_cfg:
            try:
                tools = client.get_tools(server_name=server_name)
                logger.info(
                    "mcp_tools_loaded",
                    server=server_name,
                    tool_count=len(tools),
                    tool_names=[getattr(t, "name", str(t)) for t in tools],
                )
                all_tools.extend(tools)
            except Exception as exc:
                logger.warning(
                    "mcp_tools_load_failed",
                    server=server_name,
                    error=str(exc),
                )

    return all_tools


def load_mcp_tools_sync(config_path: Path | str | None = None) -> list[Any]:
    """同步版本的 MCP 工具加载（用于非 async 上下文，如测试脚本）。

    注意：在已有 event loop 的环境（如 langgraph dev）中请用 load_mcp_tools() 异步版。
    """
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # 已有 event loop，不能直接 run —— 调用方应改用 await load_mcp_tools()
        logger.warning(
            "mcp_sync_in_async_context",
            hint="Use 'await load_mcp_tools()' instead in async context",
        )
        return []

    return asyncio.run(load_mcp_tools(config_path))


__all__ = ["load_mcp_tools", "load_mcp_tools_sync"]
