"""CTF 第一阶段 HTTP / Flag 工具封装（async via httpx）。"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import structlog
from langchain_core.tools import BaseTool, tool

logger = structlog.get_logger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 10
_DEFAULT_PREVIEW_LENGTH = 4000
_DEFAULT_LINK_LIMIT = 30

# 忽略 TLS 证书校验（CTF 靶机常用自签名证书）
_DEFAULT_VERIFY_SSL = False


def _normalize_method(method: str | None) -> str:
    normalized = (method or "GET").strip().upper()
    return normalized if normalized else "GET"


def _normalize_url(url: str, base_url: str | None = None) -> str:
    raw = (url or "").strip()
    if not raw:
        raise ValueError("URL is required")

    if raw.startswith("//"):
        return f"http:{raw}"

    parsed = urlparse(raw)
    if parsed.scheme in {"http", "https"}:
        return raw

    if base_url:
        return urljoin(base_url, raw)

    if raw.startswith("/"):
        raise ValueError("Relative URL requires base_url")

    return f"http://{raw}"


def _safe_timeout(timeout_ms: int | None) -> float:
    if timeout_ms is None:
        return float(_DEFAULT_TIMEOUT_SECONDS)
    return max(1.0, timeout_ms / 1000.0)


def _parse_headers(headers_json: str | None) -> dict[str, str]:
    if not headers_json:
        return {}
    try:
        payload = json.loads(headers_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"headers_json is invalid JSON: {exc!s}") from exc
    if not isinstance(payload, dict):
        raise ValueError("headers_json must be a JSON object")
    return {str(k): str(v) for k, v in payload.items()}


def _extract_title(text: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip()


def _extract_link_targets(text: str) -> list[str]:
    pattern = re.compile(r"(?:href|src)=[\"']([^\"']+)[\"']", flags=re.IGNORECASE)
    return [item.strip() for item in pattern.findall(text) if item.strip()]


def _extract_form_actions(text: str) -> list[str]:
    pattern = re.compile(r"<form[^>]*action=[\"']([^\"']*)[\"']", flags=re.IGNORECASE)
    return [item.strip() for item in pattern.findall(text)]


def _build_probe_summary(
    *, final_url: str, status: int, headers: dict[str, str], body: str
) -> str:
    title = _extract_title(body)
    links = _extract_link_targets(body)
    forms = _extract_form_actions(body)

    normalized_links: list[str] = []
    for link in links:
        try:
            normalized_links.append(_normalize_url(link, base_url=final_url))
        except ValueError:
            normalized_links.append(link)

    unique_links = list(dict.fromkeys(normalized_links))
    unique_forms = list(dict.fromkeys(forms))

    payload: dict[str, Any] = {
        "url": final_url,
        "status": status,
        "title": title,
        "content_type": headers.get("content-type", ""),
        "server": headers.get("server", ""),
        "link_count": len(unique_links),
        "form_count": len(unique_forms),
        "links_preview": unique_links[:_DEFAULT_LINK_LIMIT],
        "forms_preview": unique_forms[:_DEFAULT_LINK_LIMIT],
        "body_preview": body[:_DEFAULT_PREVIEW_LENGTH],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _extract_flag_candidates(text: str, extra_pattern: str | None = None) -> list[str]:
    patterns = [
        r"flag\{[^\n\r\t\f\v\{\}]{1,200}\}",
        r"ctf\{[^\n\r\t\f\v\{\}]{1,200}\}",
        r"FLAG\{[^\n\r\t\f\v\{\}]{1,200}\}",
        r"(?i)flag\s*[:=]\s*([A-Za-z0-9_\-\{\}]{4,256})",
    ]
    if extra_pattern and extra_pattern.strip():
        patterns.append(extra_pattern.strip())

    found: list[str] = []
    for pattern in patterns:
        try:
            matches = re.findall(pattern, text, flags=re.IGNORECASE)
        except re.error:
            continue
        for item in matches:
            value = "".join(str(p) for p in item if str(p)) if isinstance(item, tuple) else str(item)
            value = value.strip()
            if value:
                found.append(value)

    return list(dict.fromkeys(found))


def create_ctf_http_tools() -> tuple[BaseTool, BaseTool, BaseTool, BaseTool]:
    """创建 CTF 第一阶段工具集合（全部使用 httpx async，兼容 ASGI 事件循环）。"""

    @tool
    async def normalize_url(url: str, base_url: str | None = None) -> str:
        """规范化 URL，自动补全协议或基于 base_url 解析相对路径。"""
        try:
            return _normalize_url(url, base_url=base_url)
        except ValueError as exc:
            return f"ERROR: {exc!s}"

    @tool
    async def http_request(
        url: str,
        method: str | None = "GET",
        headers_json: str | None = None,
        body: str | None = None,
        timeout_ms: int | None = 10000,
        follow_redirects: bool | None = True,
    ) -> str:
        """发起 HTTP 请求并返回结构化摘要（状态码、响应头、正文预览）。"""
        try:
            final_url = _normalize_url(url)
            http_method = _normalize_method(method)
            timeout = _safe_timeout(timeout_ms)
            extra_headers = _parse_headers(headers_json)

            logger.info(
                "ctf_http_request_start",
                url=final_url,
                method=http_method,
                timeout_seconds=timeout,
                follow_redirects=bool(follow_redirects),
            )

            async with httpx.AsyncClient(
                verify=_DEFAULT_VERIFY_SSL,
                follow_redirects=bool(follow_redirects),
                timeout=timeout,
            ) as client:
                response = await client.request(
                    method=http_method,
                    url=final_url,
                    headers=extra_headers,
                    content=body.encode("utf-8") if body is not None else None,
                )

            response_body = response.text
            result: dict[str, Any] = {
                "success": True,
                "url": str(response.url),
                "status": response.status_code,
                "headers": dict(response.headers),
                "body_preview": response_body[:_DEFAULT_PREVIEW_LENGTH],
                "body_length": len(response_body),
            }
            return json.dumps(result, ensure_ascii=False, indent=2)

        except httpx.HTTPStatusError as exc:
            body_text = exc.response.text if exc.response is not None else ""
            result = {
                "success": False,
                "url": str(exc.request.url),
                "status": exc.response.status_code if exc.response is not None else -1,
                "error": f"HTTPStatusError: {exc!s}",
                "body_preview": body_text[:_DEFAULT_PREVIEW_LENGTH],
                "body_length": len(body_text),
            }
            return json.dumps(result, ensure_ascii=False, indent=2)
        except httpx.RequestError as exc:
            return f"ERROR: RequestError: {exc!s}"
        except ValueError as exc:
            return f"ERROR: {exc!s}"
        except Exception as exc:  # noqa: BLE001
            logger.error("ctf_http_request_exception", error=str(exc), exc_info=True)
            return f"ERROR: Failed to perform HTTP request: {exc!s}"

    @tool
    async def http_probe(url: str, timeout_ms: int | None = 10000) -> str:
        """对目标页面做轻量探测，返回标题、链接、表单等线索。"""
        try:
            final_url = _normalize_url(url)
            timeout = _safe_timeout(timeout_ms)

            async with httpx.AsyncClient(
                verify=_DEFAULT_VERIFY_SSL,
                follow_redirects=True,
                timeout=timeout,
                headers={"User-Agent": "hnksecagents-ctf-probe/1.0"},
            ) as client:
                response = await client.get(final_url)

            return _build_probe_summary(
                final_url=str(response.url),
                status=response.status_code,
                headers=dict(response.headers),
                body=response.text,
            )

        except httpx.RequestError as exc:
            return f"ERROR: RequestError: {exc!s}"
        except ValueError as exc:
            return f"ERROR: {exc!s}"
        except Exception as exc:  # noqa: BLE001
            logger.error("ctf_http_probe_exception", error=str(exc), exc_info=True)
            return f"ERROR: Failed to probe target: {exc!s}"

    @tool
    async def extract_flags(text: str, extra_pattern: str | None = None) -> str:
        """从文本中提取可能的 flag 候选值。"""
        candidates = _extract_flag_candidates(text, extra_pattern=extra_pattern)
        if not candidates:
            return "No flag candidates found"
        return json.dumps({"count": len(candidates), "flags": candidates}, ensure_ascii=False, indent=2)

    return normalize_url, http_request, http_probe, extract_flags
