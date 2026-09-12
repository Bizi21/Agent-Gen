"""Bootstrap: create the Brain structure + seed files (idempotent)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .config import Config
from .vault import Vault

SYSTEM_PROMPT = """You are Agent-Gen, a self-improving AI agent with a second brain.

You retrieve relevant knowledge from your second brain (an Obsidian vault)
before answering, use your tools when they help, and learn from your failures
via the improvement loop.

Guidelines:
- Answer in the language the user writes in.
- Cite the source of any fact you retrieve from your vault.
- When a fact is missing, say so — and let the improvement loop learn it.

## Learned lessons
"""

HOME_NOTE = """Agent-Gen is a self-improving AI agent.

It ingests external knowledge (GitHub, websites, feeds, images, scratch notes),
improves its own prompt, knowledge, and code, and is controlled through a chat
interface.

- The eval command is `/eval` — it runs the eval suite and shows a scorecard.
- The improve command is `/improve` — it runs the improvement loop.
- Long-term knowledge is stored in an **Obsidian** vault (the second brain).
- The knowledge graph ("graphify") shows notes as nodes and links as edges.
- In the config, `0` means unlimited.
"""

INBOX_README = """# 00-inbox — Capture

Everything ingested or typed lands here first, before the agent organizes it
into the rest of the vault (10-notes, 20-people, 30-projects, 40-resources).
"""

META_README = """# 90-meta — the agent's own reflections

The improvement loop writes its reflections and lesson summaries here.
"""

DEFAULT_AGENT_JSON = """{
  "gateway": {
    "default_provider": "openai",
    "default_model": "auto",
    "routing": {}
  },
  "limits": {
    "max_steps": 0,
    "max_cost_usd": 0,
    "max_context_tokens": 0,
    "rate_per_minute": 0
  },
  "autonomy": "full",
  "conversation": { "persist": true, "auto_summarize_at_tokens": 0 },
  "languages": ["en", "hi"],
  "default_lang": "auto",
  "window": { "auto_open": true, "port": 0, "title": "Agent-Gen" },
  "second_brain": { "vault_path": "./brain/vault", "graph_view": true, "open_in_obsidian": false }
}
"""


def ensure_brain(config: Config) -> None:
    """Create prompt/, config/, and the vault structure if missing (idempotent)."""
    prompt_dir = config.brain_dir / "prompt"
    prompt_dir.mkdir(parents=True, exist_ok=True)

    system_prompt = prompt_dir / "system.md"
    if not system_prompt.exists():
        system_prompt.write_text(SYSTEM_PROMPT, encoding="utf-8")

    cfg_dir = config.brain_dir / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = cfg_dir / "agent.json"
    if not cfg_file.exists():
        cfg_file.write_text(DEFAULT_AGENT_JSON, encoding="utf-8")

    vault = Vault(config.vault_path)
    # seed notes if they don't exist yet
    if not (vault.path / "10-notes" / "home.md").exists():
        vault.write_note("Agent-Gen", HOME_NOTE, folder="10-notes", filename="home.md",
                         tags=["agent-gen", "index"], meta={"language": "en"})
    if not (vault.path / "00-inbox" / "readme.md").exists():
        vault.write_note("00-inbox — Capture", INBOX_README, folder="00-inbox",
                         filename="readme.md", tags=["meta"], meta={"language": "en"})
    if not (vault.path / "90-meta" / "readme.md").exists():
        vault.write_note("90-meta — Reflections", META_README, folder="90-meta",
                         filename="readme.md", tags=["meta"], meta={"language": "en"})
