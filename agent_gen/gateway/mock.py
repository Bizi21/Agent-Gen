"""Offline deterministic mock LLM.

Used automatically when no provider key is configured, so the whole agent
runs end-to-end with zero network and zero API keys. Also used by tests.

Behavior:
* ``chat`` echoes the knowledge context the agent injected, so golden
  retrieval tasks pass when the right note is present and fail otherwise.
* ``embed`` produces deterministic hash-based vectors (no model needed).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .base import LLM, Message, Response


CONTEXT_MARKER = "KNOWLEDGE:"
TASK_MARKER = "TASK:"


class MockLLM(LLM):
    name = "mock"
    capabilities = frozenset({"chat", "embed"})

    def chat(self, messages: List[Message], tools: Optional[List[Dict]] = None) -> Response:
        last_user = ""
        for m in reversed(messages):
            if m.role == "user":
                last_user = m.content
                break

        context = ""
        if CONTEXT_MARKER in last_user:
            tail = last_user.split(CONTEXT_MARKER, 1)[1]
            context = tail.split(TASK_MARKER, 1)[0].strip()
        context = context.strip()

        if context:
            answer = "Based on my knowledge:\n\n" + context
        else:
            answer = "I don't know yet."

        return Response(content=answer, tool_calls=[])

    def complete(self, prompt: str) -> str:
        return "mock: " + prompt.strip().replace("\n", " ")[-120:]

    def embed(self, texts: List[str]) -> List[List[float]]:
        dim = 32
        vectors: List[List[float]] = []
        for text in texts:
            counts = [0.0] * dim
            for ch in text.lower():
                counts[ord(ch) % dim] += 1.0
            norm = sum(counts) or 1.0
            vectors.append([c / norm for c in counts])
        return vectors
