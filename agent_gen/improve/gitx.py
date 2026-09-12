"""Minimal git helpers (stdlib subprocess)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Optional, Tuple


class GitError(RuntimeError):
    pass


def git(root: Path, *args: str) -> Tuple[int, str, str]:
    """Run git in ``root``; return (returncode, stdout, stderr). Never raises."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError:
        return 127, "", "git not found"
    except subprocess.TimeoutExpired:
        return 124, "", "git timed out"


def is_repo(root: Path) -> bool:
    code, _, _ = git(root, "rev-parse", "--is-inside-work-tree")
    return code == 0


def head_sha(root: Path) -> Optional[str]:
    code, out, _ = git(root, "rev-parse", "HEAD")
    return out.strip() if code == 0 else None


def ensure_identity(root: Path) -> None:
    """Make sure user.name/email exist locally, so commits never fail."""
    code, out, _ = git(root, "config", "user.email")
    if code != 0 or not out.strip():
        git(root, "config", "user.email", "agent-gen@local")
    code, out, _ = git(root, "config", "user.name")
    if code != 0 or not out.strip():
        git(root, "config", "user.name", "Agent-Gen")


def commit(root: Path, paths: List[str], message: str) -> Optional[str]:
    """Stage ``paths`` and commit. Returns the new SHA, or None if nothing to commit."""
    if not is_repo(root):
        raise GitError("not a git repository")
    ensure_identity(root)
    git(root, "add", "--", *paths)
    code, out, _ = git(root, "status", "--porcelain", "--", *paths)
    if not out.strip():
        return None
    code, _, err = git(root, "commit", "-m", message)
    if code != 0:
        raise GitError(f"commit failed: {err}")
    return head_sha(root)


def discard(root: Path, paths: List[Path]) -> None:
    """Revert uncommitted changes to tracked files and delete untracked ones."""
    for p in paths:
        rel = str(p)
        code, _, _ = git(root, "ls-files", "--error-unmatch", rel)
        if code == 0:
            git(root, "checkout", "--", rel)
        else:
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass
