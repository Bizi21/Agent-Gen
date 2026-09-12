"""Google Gemini adapter — stdlib only, minimal REST (generateContent)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional

from .base import LLM, Message, Response, ToolCall


class GoogleLLM(LLM):
    name = "google"

    def __init__(self, api_key: str, model: str, timeout: float = 120.0):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _post(self, url: str, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            raise RuntimeError(f"Google request failed ({exc.code}): {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Google request error: {exc.reason}") from exc

    def chat(self, messages: List[Message], tools: Optional[List[Dict]] = None) -> Response:
        contents: List[dict] = []
        system_parts: List[str] = []
        for m in messages:
            if m.role == "system":
                system_parts.append(m.content)
                continue
            role = "model" if m.role == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": m.content}]})

        payload: dict = {
            "contents": contents,
            "generationConfig": {"temperature": 0.2},
        }
        if system_parts:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{urllib.parse.quote(self.model)}:generateContent?key={self.api_key}"
        )
        data = self._post(url, payload)
        try:
            candidates = data.get("candidates") or []
            text = ""
            for part in candidates[0].get("content", {}).get("parts", []):
                text += part.get("text", "")
            return Response(content=text, tool_calls=[], raw=data)
        except (IndexError, KeyError) as exc:
            raise RuntimeError(f"Unexpected Google response: {data}") from exc
