"""The Second Brain — an Obsidian vault of Markdown notes.

Plain Markdown + YAML frontmatter + ``[[wikilinks]]`` + ``#tags``. The agent
reads/writes/search-links these notes; the graph is derived from them.

Layout::

    vault/
      00-inbox/       capture
      10-notes/       organized knowledge
      20-people/      people & sources
      30-projects/    per-project notes
      40-resources/   raw extracted material
      90-meta/        the agent's reflections & improvement log
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

FOLDERS = ("00-inbox", "10-notes", "20-people", "30-projects", "40-resources", "90-meta")

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "what", "how",
    "why", "who", "when", "where", "which", "do", "does", "did", "for", "on", "at",
    "with", "about", "kya", "hai", "ka", "ki", "ke", "aur", "mein", "main",
}

_LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
_TAG_RE = re.compile(r"(?<!\w)#([\w-]+)")
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def slugify(text: str) -> str:
    text = re.sub(r"[^0-9a-zA-Z]+", "-", text.lower()).strip("-")
    return text or "note"


def _parse_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    meta: Dict[str, Any] = {}
    body = text
    m = _FRONTMATTER_RE.match(text)
    if m:
        body = text[m.end():]
        for line in m.group(1).splitlines():
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            value = value.strip()
            key = key.strip()
            if value.startswith("[") and value.endswith("]"):
                value = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
            else:
                value = value.strip("'\"")
            meta[key] = value
    return meta, body


def _render_frontmatter(meta: Dict[str, Any]) -> str:
    if not meta:
        return ""
    lines = ["---"]
    for key, value in meta.items():
        if isinstance(value, (list, tuple)):
            lines.append(f"{key}: [{', '.join(str(v) for v in value)}]")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines) + "\n"


@dataclass
class Note:
    relpath: str
    title: str
    body: str
    meta: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)


class Vault:
    """An Obsidian vault the agent reads and writes."""

    def __init__(self, path: Path | str):
        self.path = Path(path).resolve()
        self.ensure_structure()

    def ensure_structure(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        for folder in FOLDERS:
            (self.path / folder).mkdir(parents=True, exist_ok=True)
        # Obsidian metadata dir (ignored by our .md listing)
        (self.path / ".obsidian").mkdir(exist_ok=True)

    # -- read/write ------------------------------------------------------- #
    def write_note(
        self,
        title: str,
        body: str,
        folder: str = "10-notes",
        filename: Optional[str] = None,
        tags: Optional[List[str]] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Path:
        folder = folder if folder in FOLDERS else "10-notes"
        filename = filename or (slugify(title) + ".md")
        if not filename.endswith(".md"):
            filename += ".md"
        target = self.path / folder / filename
        meta = dict(meta or {})
        meta.setdefault("title", title)
        meta.setdefault("created", time.strftime("%Y-%m-%d", time.gmtime()))
        meta.setdefault("tags", tags or [])
        meta.setdefault("language", meta.get("language", "en"))
        text = _render_frontmatter(meta)
        text += f"# {title}\n\n{body.strip()}\n"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def read_note(self, relpath: str) -> Optional[Note]:
        path = self.path / relpath
        if not path.is_file():
            return None
        return self.parse(path)

    def parse(self, path: Path) -> Note:
        text = path.read_text(encoding="utf-8", errors="replace")
        meta, body = _parse_frontmatter(text)
        title = str(meta.get("title") or path.stem.replace("-", " ").title())
        links = [m.strip() for m in _LINK_RE.findall(text)]
        tags = list(dict.fromkeys(_TAG_RE.findall(text)))
        if isinstance(meta.get("tags"), list):
            tags = list(dict.fromkeys([str(t) for t in meta["tags"]] + tags))
        return Note(
            relpath=str(path.relative_to(self.path)),
            title=title,
            body=body.strip(),
            meta=meta,
            tags=tags,
            links=links,
        )

    def list_notes(self) -> List[Path]:
        paths = []
        for folder in FOLDERS:
            d = self.path / folder
            if d.is_dir():
                paths.extend(sorted(d.rglob("*.md")))
        return paths

    def note_titles(self) -> Dict[str, str]:
        """title-slug -> relpath index for resolving wikilinks."""
        index: Dict[str, str] = {}
        for p in self.list_notes():
            note = self.parse(p)
            index[slugify(note.title)] = note.relpath
            index[slugify(p.stem)] = note.relpath
        return index

    # -- retrieval -------------------------------------------------------- #
    def search(self, query: str, top_k: int = 5) -> List[Tuple[Note, float]]:
        tokens = [
            t for t in re.findall(r"[a-zA-Z0-9]+", query.lower())
            if len(t) > 2 and t not in STOPWORDS
        ]
        if not tokens:
            tokens = re.findall(r"[a-zA-Z0-9]+", query.lower())

        scored: List[Tuple[Note, float]] = []
        for path in self.list_notes():
            note = self.parse(path)
            hay = (note.title + "\n" + note.body).lower()
            score = 0.0
            for t in tokens:
                if t in hay:
                    score += 1.0
                if t in path.stem.lower():
                    score += 0.5
            if score > 0:
                scored.append((note, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]

    # -- graph ------------------------------------------------------------ #
    def graph(self) -> Dict[str, Any]:
        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, str]] = []
        title_index = self.note_titles()

        def node_id(relpath: str) -> str:
            return relpath.replace("/", "__").replace(".md", "")

        for path in self.list_notes():
            note = self.parse(path)
            nid = node_id(note.relpath)
            nodes[nid] = {
                "id": nid,
                "title": note.title,
                "folder": note.relpath.split("/")[0],
                "tags": note.tags,
                "relpath": note.relpath,
            }
            for link in note.links:
                target = title_index.get(slugify(link))
                if target:
                    edges.append({"source": nid, "target": node_id(target), "kind": "link"})
            for tag in note.tags:
                tid = "tag:" + tag
                nodes.setdefault(tid, {"id": tid, "title": "#" + tag, "folder": "tag",
                                       "tags": [], "relpath": None})
                edges.append({"source": nid, "target": tid, "kind": "tag"})

        # dedupe edges
        seen = set()
        unique_edges = []
        for e in edges:
            key = (e["source"], e["target"])
            if key in seen:
                continue
            seen.add(key)
            unique_edges.append(e)

        return {"nodes": list(nodes.values()), "edges": unique_edges}

    # -- capture ---------------------------------------------------------- #
    def add_to_inbox(self, text: str, title: Optional[str] = None, source: Optional[str] = None) -> Path:
        title = title or ("capture-" + time.strftime("%Y%m%d-%H%M%S"))
        meta = {"language": "auto"}
        if source:
            meta["source"] = source
        return self.write_note(title=title, body=text, folder="00-inbox",
                               filename=slugify(title) + ".md", meta=meta)
