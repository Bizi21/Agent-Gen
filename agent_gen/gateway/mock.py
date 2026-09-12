"""Offline deterministic mock LLM.

Used automatically when no provider key is configured, so the whole agent
runs end-to-end with zero network and zero API keys. Also used by tests.

Behavior:
* Plain questions echo the knowledge context the agent injected, so golden
  retrieval tasks pass when the right note is present and fail otherwise.
* Commands containing action verbs (search / find / list / files / ingest)
  trigger real tool calls, so the loop's tools run live even offline.
* ``embed`` produces deterministic hash-based vectors (no model needed).
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from .base import LLM, Message, Response, ToolCall


CONTEXT_MARKER = "KNOWLEDGE:"
TASK_MARKER = "TASK:"

_URL_RE = re.compile(r"https?://\S+")
_WORD_RE = re.compile(r"\b(search|find|list|files|ingest)\b")


class MockLLM(LLM):
    name = "mock"
    capabilities = frozenset({"chat", "embed"})

    def chat(self, messages: List[Message], tools: Optional[List[Dict]] = None) -> Response:
        # 1) If a tool already ran, answer from its result.
        tool_results = [m for m in messages if m.role == "tool"]
        if tool_results:
            last = tool_results[-1].content
            return Response(content="Used a tool. Result:\n\n" + last[:2000], tool_calls=[])

        # 2) Find the last user message and split context vs. task.
        last_user = ""
        for m in reversed(messages):
            if m.role == "user":
                last_user = m.content
                break

        context = ""
        task_text = last_user
        if CONTEXT_MARKER in last_user:
            head, _, tail = last_user.partition(TASK_MARKER)
            context = head.split(CONTEXT_MARKER, 1)[1].strip()
            task_text = tail.strip()

        # 3) Tool directives, decided on the actual task text (not the context).
        if tools:
            names = {spec["name"] for spec in tools}
            verbs = _WORD_RE.findall(task_text.lower())
            if "vault_search" in names and any(v in {"search", "find"} for v in verbs):
                return Response(
                    "",
                    tool_calls=[ToolCall(id="mock-1", name="vault_search",
                                         arguments={"query": task_text, "top_k": 3})],
                )
            if "list_dir" in names and any(v in {"list", "files"} for v in verbs):
                return Response(
                    "",
                    tool_calls=[ToolCall(id="mock-1", name="list_dir", arguments={"path": "."})],
                )
            if "ingest_url" in names and "ingest" in verbs:
                url = _URL_RE.search(task_text)
                if url:
                    return Response(
                        "",
                        tool_calls=[ToolCall(id="mock-1", name="ingest_url",
                                             arguments={"url": url.group(0)})],
                    )

        # 4) Default: echo the injected knowledge context.
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
