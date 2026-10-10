"""阶跃星辰 StepFun 聊天客户端（OpenAI 兼容）。

只依赖 httpx，不装 openai sdk。
base_url: https://api.stepfun.com/v1
可用对话模型（2026-10 实测 /v1/models）：step-3.5-flash、step-3.7-flash、
step-5-preview、step-gui、step-1o-turbo-vision、step-router-v1。
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://api.stepfun.com/v1"
DEFAULT_MODEL = "step-3.5-flash"


class StepFunError(RuntimeError):
    def __init__(self, message: str, *, http_status: int | None = None):
        super().__init__(message)
        self.http_status = http_status


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatReply:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, Any] = field(default_factory=dict)

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


class StepFunClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        *,
        timeout: float = 60.0,
        max_retries_on_429: int = 3,
    ):
        key = api_key or os.environ.get("STEPFUN_API_KEY") or ""
        if not key.strip():
            raise StepFunError("缺少 STEPFUN_API_KEY：请写入 .env 或设置环境变量")
        self._key = key.strip()
        self.model = model or os.environ.get("STEPFUN_MODEL") or DEFAULT_MODEL
        self.base_url = (base_url or os.environ.get("STEPFUN_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self._max_retries = max_retries_on_429
        self._http = httpx.Client(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {self._key}",
                "Content-Type": "application/json",
            },
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "StepFunClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ---------- 模型清单 ----------

    def models(self, only_chat: bool = True) -> list[dict[str, Any]]:
        response = self._request("GET", "/models")
        data = response.get("data") or []
        if not only_chat:
            return data
        return [
            item
            for item in data
            if item.get("model_type") == "大语言模型"
            and "chat" in (item.get("supported_protocols") or [])
        ]

    # ---------- 对话 ----------

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = "auto",
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> ChatReply:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            if tool_choice:
                payload["tool_choice"] = tool_choice
        if max_tokens:
            payload["max_tokens"] = max_tokens

        response = self._request("POST", "/chat/completions", json_body=payload)
        choices = response.get("choices") or []
        if not choices:
            return ChatReply(raw=response)
        message = choices[0].get("message") or {}

        calls: list[ToolCall] = []
        for raw_call in message.get("tool_calls") or []:
            function = raw_call.get("function") or {}
            raw_args = function.get("arguments") or "{}"
            try:
                arguments = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
            except json.JSONDecodeError:
                arguments = {}
            calls.append(
                ToolCall(id=raw_call.get("id", ""), name=function.get("name", ""), arguments=arguments)
            )

        return ChatReply(
            text=message.get("content") or "",
            tool_calls=calls,
            raw=response,
            usage=response.get("usage") or {},
        )

    # ---------- 传输 ----------

    def _request(
        self, method: str, path: str, *, json_body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        for attempt in range(self._max_retries + 1):
            try:
                response = (
                    self._http.post(url, json=json_body)
                    if method == "POST"
                    else self._http.get(url)
                )
            except httpx.HTTPError as exc:
                if attempt >= self._max_retries:
                    raise StepFunError(f"网络请求失败：{exc}") from exc
                time.sleep(2 ** attempt)
                continue

            if response.status_code == 401:
                raise StepFunError("阶跃星辰 API Key 无效或已过期（HTTP 401）。", http_status=401)
            if response.status_code == 429:
                if attempt >= self._max_retries:
                    raise StepFunError("触发限流（HTTP 429）。", http_status=429)
                time.sleep(2 ** attempt)
                continue
            if response.status_code >= 400:
                raise StepFunError(
                    f"阶跃星辰返回 HTTP {response.status_code}：{response.text[:300]}",
                    http_status=response.status_code,
                )
            if not response.text.strip():
                return {}
            return response.json()

        raise StepFunError("请求失败且已重试多次")
