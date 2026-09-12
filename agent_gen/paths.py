"""Path helpers: locate the repository root and standard directories."""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    """Absolute path of the Agent-Gen repository root (parent of this package)."""
    return Path(__file__).resolve().parent.parent


def brain_dir(root: Path | None = None) -> Path:
    root = root or repo_root()
    return root / "brain"
