"""Resilient LLM wrapper: try the real provider, fall back to offline mock.

If the primary adapter raises (network blocked, quota, invalid key, …), the
wrapper logs one warning and transparently serves the fallback for the rest of
the process. The agent never crashes just because a provider is unreachable.
"""

from __future__ import annotations

import sys
from typing import Dict, List, Optional

from .base import LLM, Message, Response
from .mock import MockLLM


class ResilientLLM(LLM):
    def __init__(self, primary: LLM, fallback: Optional[LLM] = None):
        self.primary = primary
        self.fallback = fallback or MockLLM()
        self.degraded = False
        self.last_error: Optional[Exception] = None
        self.capabilities = self.primary.capabilities | self.fallback.capabilities

    @property
    def name(self) -> str:
        return getattr(self.primary, "name", type(self.primary).__name__)

    def _call(self, method: str, *args, **kwargs):
        if not self.degraded:
            try:
                return getattr(self.primary, method)(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - resilience boundary
                self.degraded = True
                self.last_error = exc
                print(
                    f"[gateway] {self.name} unreachable "
                    f"({type(exc).__name__}: {exc}) -> falling back to offline mock",
                    file=sys.stderr,
                )
        return getattr(self.fallback, method)(*args, **kwargs)

    def chat(self, messages: List[Message], tools: Optional[List[Dict]] = None) -> Response:
        return self._call("chat", messages, tools=tools)

    def complete(self, prompt: str) -> str:
        return self._call("complete", prompt)

    def embed(self, texts: List[str]) -> List[List[float]]:
        return self._call("embed", texts)

    def describe_image(self, image_bytes: bytes, prompt: str = "") -> str:
        return self._call("describe_image", image_bytes, prompt=prompt)
