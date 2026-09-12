"""Anthropic (Claude) adapter — stdlib only."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Dict, List, Optional

from .base import LLM, Message, Response, ToolCall, dumps, to_tool_schema


class AnthropicLLM(LLM):
    name = "anthropic"

    def __init__(self, api_key: str, model: str, timeout: float = 120.0):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _post(self, payload: dict) -> dict:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            raise RuntimeError(f"Anthropic request failed ({exc.code}): {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Anthropic request error: {exc.reason}") from exc

    def chat(self, messages: List[Message], tools: Optional[List[Dict]] = None) -> Response:
        system_parts = [m.content for m in messages if m.role == "system"]
        system = "\n\n".join(system_parts) if system_parts else None

        payload: dict = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [
                {"role": "user" if m.role in ("user", "tool") else "assistant", "content": m.content}
                for m in messages
                if m.role != "system"
            ],
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = [to_tool_schema(t) for t in tools]

        data = self._post(payload)

        content = ""
        tool_calls: List[ToolCall] = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.get("id", ""),
                        name=block.get("name", ""),
                        arguments=block.get("input") or {},
                    )
                )
        return Response(content=content, tool_calls=tool_calls, raw=data)
