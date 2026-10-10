"""麦当劳 MCP Streamable HTTP 客户端（零依赖第三方 MCP SDK）。

协议要点（MCP Streamable HTTP transport）：
  1. POST <url>，头部带 Authorization: Bearer <token>，
     Accept 同时声明 application/json 与 text/event-stream。
  2. initialize 响应的 `mcp-session-id` 头必须回带在后续所有请求上。
  3. 之后 POST 一次 notifications/initialized（无 id，属于通知）。
  4. tools/list 拿工具清单与 inputSchema；tools/call 调工具。
  5. 响应可能是单条 JSON，也可能是 SSE 流（text/event-stream）——两种都要能解析。

限流：官方限制 600 次/分钟/Token，这里默认按 540 做客户端滑动窗口限流。
"""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import httpx

MCP_PROTOCOL_VERSION = "2025-06-18"
CLIENT_INFO = {"name": "maimai-monster", "version": "0.1.0"}


class McpError(RuntimeError):
    """MCP 调用失败。http_status 用于区分 401（Token 失效）与 429（限流）。"""

    def __init__(self, message: str, *, http_status: int | None = None, code: int | None = None):
        super().__init__(message)
        self.http_status = http_status
        self.code = code


@dataclass
class Tool:
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)

    @property
    def required_args(self) -> list[str]:
        return list(self.input_schema.get("required", []) or [])

    @property
    def arg_names(self) -> list[str]:
        return list((self.input_schema.get("properties") or {}).keys())


@dataclass
class ToolResult:
    """一次 tools/call 的结果。text 是原始文本，data 是它能解析成 JSON 时的结构。"""

    name: str
    raw: dict[str, Any]
    text: str
    data: Any = None
    is_error: bool = False

    def raise_for_error(self) -> "ToolResult":
        if self.is_error:
            raise McpError(f"工具 {self.name} 返回错误：{self.text[:400]}")
        return self

    _WRAPPER_MARKERS = frozenset({"success", "code", "message", "traceId"})

    def unwrap(self) -> Any:
        """剥掉麦当劳统一响应壳，返回真正的业务体。

        真实返回实测形如 `{"success":true,"code":200,"data":[...]}`，
        也可能是 `[{"success":true,...,"data":{...}}]`（包一层数组）。

        注意：**只剥壳，不折叠 data 本身**。query-store-coupons 的 data 就是
        一张券的列表，长度恰好为 1 时如果顺手折叠掉，调用方会拿到券对象而不是列表。
        """
        node: Any = self.data
        if isinstance(node, dict) and "data" in node and set(node) & self._WRAPPER_MARKERS:
            return node["data"]
        if (
            isinstance(node, list)
            and len(node) == 1
            and isinstance(node[0], dict)
            and "data" in node[0]
            and set(node[0]) & self._WRAPPER_MARKERS
        ):
            return node[0]["data"]
        return node

    @property
    def ok(self) -> bool:
        """响应壳里的 success 标记。没有壳（或壳里没这个字段）时按 True 处理。"""
        node = self.data
        if isinstance(node, list) and len(node) == 1:
            node = node[0]
        if isinstance(node, dict) and "success" in node:
            return bool(node["success"])
        return True

    @property
    def error_message(self) -> str:
        node = self.data
        if isinstance(node, list) and len(node) == 1:
            node = node[0]
        if isinstance(node, dict) and not node.get("success", True):
            return str(node.get("message") or node.get("code") or "未知错误")
        return ""

    def as_list(self) -> list[Any]:
        """宽容适配：壳 → data → 里面的第一个列表。"""
        node = self.unwrap()
        if isinstance(node, list):
            return node
        if isinstance(node, dict):
            preferred = (
                "items", "list", "records", "result", "coupons", "meals", "stores",
                "addresses", "foods", "nutritionList", "mealList", "couponList",
            )
            for key in preferred:
                value = node.get(key)
                if isinstance(value, list):
                    return value
            for value in node.values():
                if isinstance(value, list):
                    return value
            return [node] if node else []
        return []


class _RateLimiter:
    """滑动窗口限流，线程安全。"""

    def __init__(self, limit_per_minute: int):
        self.limit = max(1, limit_per_minute)
        self._hits: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                while self._hits and now - self._hits[0] >= 60.0:
                    self._hits.popleft()
                if len(self._hits) < self.limit:
                    self._hits.append(now)
                    return
                sleep_for = 60.0 - (now - self._hits[0]) + 0.05
            time.sleep(max(sleep_for, 0.05))


class McdMcpClient:
    """麦当劳 MCP 客户端。线程安全，可跨 QTimer 回调复用。"""

    def __init__(
        self,
        token: str,
        url: str | None = None,
        *,
        timeout: float = 30.0,
        rate_limit_per_minute: int = 540,
        max_retries_on_429: int = 3,
    ):
        if not token or not str(token).strip():
            raise McpError("缺少 MCP Token：请设置环境变量 MCD_MCP_TOKEN")
        self._token = str(token).strip()
        self._url = url or "https://mcp.mcd.cn"
        self._session_id: str | None = None
        self._initialized = False
        self._id = 0
        self._lock = threading.Lock()
        self._limiter = _RateLimiter(rate_limit_per_minute)
        self._max_retries = max_retries_on_429
        self._http = httpx.Client(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )

    # ---------- 生命周期 ----------

    def __enter__(self) -> "McdMcpClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    @property
    def session_id(self) -> str | None:
        return self._session_id

    def _next_id(self) -> int:
        with self._lock:
            self._id += 1
            return self._id

    def _headers(self) -> dict[str, str]:
        headers = {"MCP-Protocol-Version": MCP_PROTOCOL_VERSION}
        if self._session_id:
            headers["mcp-session-id"] = self._session_id
        return headers

    def _post(self, payload: dict[str, Any]) -> httpx.Response:
        self._limiter.acquire()
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = self._http.post(self._url, json=payload, headers=self._headers())
            except httpx.HTTPError as exc:  # 网络层失败
                last_error = exc
                if attempt >= self._max_retries:
                    raise McpError(f"网络请求失败：{exc}") from exc
                time.sleep(2 ** attempt)
                continue

            if response.status_code == 401:
                raise McpError(
                    "MCP Token 无效、已过期或未提供（HTTP 401）。"
                    "请到 https://open.mcd.cn/mcp 控制台重新激活。",
                    http_status=401,
                )
            if response.status_code == 429:
                if attempt >= self._max_retries:
                    raise McpError("触发限流（HTTP 429，600 次/分钟）。", http_status=429)
                retry_after = response.headers.get("Retry-After")
                try:
                    delay = float(retry_after) if retry_after else 2 ** attempt
                except ValueError:
                    delay = 2 ** attempt
                time.sleep(max(delay, 0.5))
                continue
            if response.status_code >= 400:
                raise McpError(
                    f"MCP 服务返回 HTTP {response.status_code}：{response.text[:300]}",
                    http_status=response.status_code,
                )

            new_session = response.headers.get("mcp-session-id")
            if new_session:
                self._session_id = new_session
            return response

        raise McpError(f"请求失败且已重试 {self._max_retries} 次：{last_error}")

    # ---------- 响应解析 ----------

    @staticmethod
    def _extract_messages(response: httpx.Response) -> list[dict[str, Any]]:
        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            messages: list[dict[str, Any]] = []
            for line in response.text.splitlines():
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                body = line[len("data:"):].strip()
                if not body:
                    continue
                try:
                    messages.append(json.loads(body))
                except json.JSONDecodeError:
                    continue
            return messages
        if not response.text.strip():
            return []
        payload = response.json()
        return [payload] if isinstance(payload, dict) else list(payload)

    def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        request_id = self._next_id()
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        response = self._post(payload)
        messages = self._extract_messages(response)

        for message in messages:
            if message.get("id") == request_id:
                if "error" in message:
                    error = message["error"]
                    raise McpError(
                        f"{method} 失败：{error.get('message', error)}",
                        code=error.get("code"),
                    )
                return message.get("result") or {}
        # 服务端可能省略 id（罕见）。退而求其次取最后一条非错误消息。
        for message in reversed(messages):
            if "error" in message:
                error = message["error"]
                raise McpError(f"{method} 失败：{error.get('message', error)}", code=error.get("code"))
            if "result" in message:
                return message["result"] or {}
        return {}

    def _notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        self._post(payload)

    # ---------- 对外 API ----------

    def initialize(self) -> dict[str, Any]:
        result = self._request(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": CLIENT_INFO,
            },
        )
        self._notify("notifications/initialized")
        self._initialized = True
        return result

    def ensure_initialized(self) -> None:
        if not self._initialized:
            self.initialize()

    def list_tools(self) -> list[Tool]:
        self.ensure_initialized()
        result = self._request("tools/list")
        tools: list[Tool] = []
        for item in result.get("tools", []) or []:
            tools.append(
                Tool(
                    name=item.get("name", ""),
                    description=item.get("description", "") or "",
                    input_schema=item.get("inputSchema") or {},
                )
            )
        return tools

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> ToolResult:
        self.ensure_initialized()
        result = self._request("tools/call", {"name": name, "arguments": arguments or {}})

        content = result.get("content") or []
        texts = [str(block.get("text", "")) for block in content if isinstance(block, dict)]
        text = "\n".join(t for t in texts if t).strip()

        data: Any = None
        if text:
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = None
        if data is None and isinstance(result.get("structuredContent"), dict):
            data = result["structuredContent"]

        return ToolResult(
            name=name,
            raw=result,
            text=text,
            data=data,
            is_error=bool(result.get("isError")),
        )
