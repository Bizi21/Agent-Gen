"""OpenAI-compatible HTTP adapter (stdlib only).

Covers OpenAI, Groq, DeepSeek, Together, OpenRouter, Mistral, Cohere, Ollama,
LM Studio, vLLM, and any custom endpoint that speaks the OpenAI schema.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Dict, List, Optional

from .base import LLM, Message, Response, ToolCall, dumps, to_tool_schema


class OpenAICompatLLM(LLM):
    name = "openai-compatible"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        *,
        embed_model: Optional[str] = None,
        capabilities: frozenset = frozenset({"chat", "embed"}),
        timeout: float = 120.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.embed_model = embed_model or model
        self.capabilities = capabilities
        self.timeout = timeout

    # -- HTTP ------------------------------------------------------------- #
    def _post(self, path: str, payload: dict) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            raise RuntimeError(f"LLM request failed ({exc.code}): {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"LLM request error: {exc.reason}") from exc

    # -- chat ------------------------------------------------------------- #
    def chat(self, messages: List[Message], tools: Optional[List[Dict]] = None) -> Response:
        payload: dict = {
            "model": self.model,
            "messages": [_message_to_openai(m) for m in messages],
        }
        if tools:
            payload["tools"] = [to_tool_schema(t) for t in tools]
            payload["tool_choice"] = "auto"

        data = self._post("/chat/completions", payload)
        try:
            choice = data["choices"][0]["message"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Unexpected chat response: {data}") from exc

        content = choice.get("content") or ""
        tool_calls: List[ToolCall] = []
        for tc in choice.get("tool_calls") or []:
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(id=tc.get("id", ""), name=fn.get("name", ""), arguments=args))

        return Response(content=content, tool_calls=tool_calls, raw=data)

    # -- embeddings ------------------------------------------------------- #
    def embed(self, texts: List[str]) -> List[List[float]]:
        data = self._post("/embeddings", {"model": self.embed_model, "input": texts})
        try:
            items = sorted(data["data"], key=lambda d: d.get("index", 0))
            return [item["embedding"] for item in items]
        except (KeyError, TypeError) as exc:
            raise RuntimeError(f"Unexpected embedding response: {data}") from exc

    def describe_image(self, image_bytes: bytes, prompt: str = "") -> str:
        import base64

        b64 = base64.b64encode(image_bytes).decode("ascii")
        content = [{"type": "text", "text": prompt or "Describe this image."}]
        content.append(
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
        )
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
        }
        data = self._post("/chat/completions", payload)
        try:
            return data["choices"][0]["message"].get("content") or ""
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Unexpected vision response: {data}") from exc


def _message_to_openai(m: Message) -> dict:
    out: dict = {"role": m.role, "content": m.content}
    if m.tool_calls:
        out["tool_calls"] = [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.name, "arguments": dumps(tc.arguments)}}
            for tc in m.tool_calls
        ]
    if m.role == "tool" and m.tool_call_id:
        out["tool_call_id"] = m.tool_call_id
    if m.name:
        out["name"] = m.name
    return out
