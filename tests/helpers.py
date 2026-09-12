"""Shared test helpers."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Tuple

from agent_gen.agent import Agent
from agent_gen.bootstrap import ensure_brain
from agent_gen.config import Config
from agent_gen.gateway.mock import MockLLM
from agent_gen.memory.store import Memory
from agent_gen.vault import Vault


def make_tmp_root() -> Path:
    root = Path(tempfile.mkdtemp(prefix="agent-gen-test-"))
    return root


def git_init(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@agent-gen.local"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Agent-Gen Test"], check=True)


def make_runtime(root: Path, with_git: bool = True) -> Tuple[Config, Vault, Memory, Agent]:
    """Build a full offline runtime rooted at ``root``."""
    if with_git:
        git_init(root)
    config = Config.load(root)
    ensure_brain(config)
    vault = Vault(config.vault_path)
    memory = Memory(config.memory_path)
    agent = Agent(config, MockLLM(), vault, memory)
    return config, vault, memory, agent
