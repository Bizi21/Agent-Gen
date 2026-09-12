"""Base types and interface for LLM providers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Message:
    role: str  # system | user | assistant | tool
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List["ToolCall"]] = None
    tool_call_id: Optional[str] = None


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    tool_call_id: str
    name: str
    content: str


@dataclass
class Response:
    content: str
    tool_calls: List[ToolCall] = field(default_factory=list)
    raw: Any = None


def to_tool_schema(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize an internal tool spec to a JSON-schema-ish OpenAI tool."""
    return {
        "type": "function",
        "function": {
            "name": spec["name"],
            "description": spec.get("description", ""),
            "parameters": {
                "type": "object",
                "properties": spec.get("parameters", {}),
                "required": spec.get("required", []),
            },
        },
    }


class LLM:
    """Interface every provider adapter implements.

    Only ``chat`` is strictly required. ``embed`` / ``describe_image`` raise
    ``NotImplementedError`` unless the adapter supports them.
    """

    name: str = "base"
    capabilities: frozenset = frozenset({"chat"})

    def chat(self, messages: List[Message], tools: Optional[List[Dict[str, Any]]] = None) -> Response:
        raise NotImplementedError

    def complete(self, prompt: str) -> str:
        return self.chat([Message(role="user", content=prompt)]).content

    def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError(f"{self.name} does not support embeddings")

    def describe_image(self, image_bytes: bytes, prompt: str = "") -> str:
        raise NotImplementedError(f"{self.name} does not support vision")

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<{type(self).__name__} name={self.name}>"


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)
