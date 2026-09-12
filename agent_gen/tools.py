"""Tool layer: definitions + execution.

Each tool is described by a JSON-schema-ish spec (so it can be passed to any
LLM's tool-calling API) and an executor function. Tools operate on the vault,
filesystem, and memory.
"""

from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .memory.store import Memory
from .vault import Vault

# --------------------------------------------------------------------------- #
# Context passed to every tool executor
# --------------------------------------------------------------------------- #


@dataclass
class ToolContext:
    vault: Vault
    memory: Memory
    root: Path
    extra: Dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Executors
# --------------------------------------------------------------------------- #

def _read_file(ctx: ToolContext, path: str) -> str:
    p = (ctx.root / path).resolve()
    if not p.is_file():
        return f"ERROR: file not found: {path}"
    return p.read_text(encoding="utf-8", errors="replace")


def _write_file(ctx: ToolContext, path: str, content: str) -> str:
    p = (ctx.root / path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} chars to {path}"


def _edit_file(ctx: ToolContext, path: str, old_text: str, new_text: str) -> str:
    p = (ctx.root / path).resolve()
    if not p.is_file():
        return f"ERROR: file not found: {path}"
    content = p.read_text(encoding="utf-8", errors="replace")
    if old_text not in content:
        return f"ERROR: old_text not found in {path}"
    p.write_text(content.replace(old_text, new_text, 1), encoding="utf-8")
    return f"Edited {path} (1 replacement)"


def _list_dir(ctx: ToolContext, path: str = ".") -> str:
    p = (ctx.root / path).resolve()
    if not p.is_dir():
        return f"ERROR: directory not found: {path}"
    entries = sorted(str(e.relative_to(p)) for e in p.iterdir())
    return "\n".join(entries) or "(empty)"


def _vault_search(ctx: ToolContext, query: str, top_k: int = 5) -> str:
    results = ctx.vault.search(query, top_k=top_k)
    if not results:
        return "(no matching notes)"
    lines = []
    for note, score in results:
        lines.append(f"## {note.title} ({note.relpath}, score={score:.1f})\n{note.body}")
    return "\n\n".join(lines)


def _vault_write_note(
    ctx: ToolContext,
    title: str,
    body: str,
    folder: str = "10-notes",
    tags: Optional[List[str]] = None,
) -> str:
    p = ctx.vault.write_note(title=title, body=body, folder=folder, tags=tags)
    return f"Wrote note {p.relative_to(ctx.vault.path)}"


def _ingest_url(ctx: ToolContext, url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Agent-Gen/0.1"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    text = _html_to_text(raw)
    title = _html_title(raw) or url
    p = ctx.vault.add_to_inbox(text[:20000], title=f"web: {title}", source=url)
    return f"Ingested {len(text)} chars from {url} into {p.relative_to(ctx.vault.path)}"


def _remember(ctx: ToolContext, note: str) -> str:
    ctx.memory.log("remember", {"text": note})
    return f"Remembered ({len(note)} chars)"


def _now(_ctx: ToolContext) -> str:
    import time
    return time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime())


def _html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    html = re.sub(r"&nbsp;?", " ", html)
    html = re.sub(r"&amp;", "&", html)
    html = re.sub(r"&#39;|&apos;", "'", html)
    html = re.sub(r"&quot;", '"', html)
    html = re.sub(r"&lt;", "<", html)
    html = re.sub(r"&gt;", ">", html)
    html = re.sub(r"[ \t]+", " ", html)
    return re.sub(r"\n\s*\n+", "\n\n", html).strip()


def _html_title(html: str) -> str:
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    return m.group(1).strip() if m else ""


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #

@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    required: List[str] = field(default_factory=list)
    executor: Callable[[ToolContext, Any], str] = None  # type: ignore[assignment]


TOOLS: Dict[str, ToolSpec] = {}


def _register(spec: ToolSpec) -> ToolSpec:
    TOOLS[spec.name] = spec
    return spec


_register(ToolSpec("read_file", "Read a file's contents.", {"path": {"type": "string"}}, ["path"], _read_file))
_register(ToolSpec("write_file", "Create/overwrite a file.", {
    "path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"], _write_file))
_register(ToolSpec("edit_file", "Replace the first occurrence of old_text with new_text in a file.", {
    "path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}},
    ["path", "old_text", "new_text"], _edit_file))
_register(ToolSpec("list_dir", "List a directory.", {"path": {"type": "string"}}, [], _list_dir))
_register(ToolSpec("vault_search", "Search the second-brain vault.", {
    "query": {"type": "string"}, "top_k": {"type": "integer"}}, ["query"], _vault_search))
_register(ToolSpec("vault_write_note", "Write a note into the second-brain vault.", {
    "title": {"type": "string"}, "body": {"type": "string"}, "folder": {"type": "string"},
    "tags": {"type": "array", "items": {"type": "string"}}}, ["title", "body"], _vault_write_note))
_register(ToolSpec("ingest_url", "Fetch a URL and file its text into the inbox.", {
    "url": {"type": "string"}}, ["url"], _ingest_url))
_register(ToolSpec("remember", "Store a durable memory in the episodic log.", {
    "note": {"type": "string"}}, ["note"], _remember))
_register(ToolSpec("now", "Get the current date and time.", {}, [], _now))


def tool_schemas() -> List[Dict[str, Any]]:
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "parameters": spec.parameters,
            "required": spec.required,
        }
        for spec in TOOLS.values()
    ]


def execute(name: str, args: Dict[str, Any], ctx: ToolContext) -> str:
    spec = TOOLS.get(name)
    if spec is None or spec.executor is None:
        return f"ERROR: unknown tool '{name}'"
    try:
        return str(spec.executor(ctx, args))
    except Exception as exc:  # noqa: BLE001 - tools must never crash the loop
        return f"ERROR executing {name}: {type(exc).__name__}: {exc}"
