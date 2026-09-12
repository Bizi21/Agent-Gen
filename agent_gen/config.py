"""Configuration loader.

Two sources, split by sensitivity:

* ``.env``            — secrets: API keys, endpoints, local model URLs (gitignored).
* ``config/agent.json`` — non-secrets: routing, limits, autonomy, languages, window.

``.env`` values override ``agent.json`` values, which override built-in
defaults. Every limit accepts ``0`` / ``none`` to mean "unlimited".
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .paths import brain_dir, repo_root


# --------------------------------------------------------------------------- #
# Small .env parser (stdlib only, no external dependency)
# --------------------------------------------------------------------------- #
def parse_env_file(path: Path) -> Dict[str, str]:
    """Parse a KEY=VALUE ``.env`` file. ``#`` starts a comment. No quoting magic."""
    out: Dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        # strip inline comments (naive: ' #' after value)
        if " #" in value:
            value = value.split(" #", 1)[0].strip()
        out[key] = value
    return out


def _to_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


def _to_int(value: Any, default: int = 0) -> int:
    if value is None or str(value).strip().lower() in {"", "none"}:
        return default
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _to_list(value: Any, default: List[str] | None = None) -> List[str]:
    if value is None:
        return list(default or [])
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value]
    return list(default or [])


# Known provider name -> environment variable that holds its API key.
PROVIDER_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "groq": "GROQ_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "cohere": "COHERE_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "together": "TOGETHER_API_KEY",
    "azure": "AZURE_OPENAI_API_KEY",
    "custom": "CUSTOM_API_KEY",
    "ollama": None,  # no key required
}

# Default base URLs for OpenAI-compatible providers.
PROVIDER_BASE_URL = {
    "openai": "https://api.openai.com/v1",
    "mistral": "https://api.mistral.ai/v1",
    "groq": "https://api.groq.com/openai/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "together": "https://api.together.xyz/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "cohere": "https://api.cohere.com/v1",
    "ollama": "http://localhost:11434/v1",
    "custom": "",
}

CAPABILITIES = ("chat", "reflect", "summarize", "judge", "vision", "embedding")


@dataclass
class Config:
    """Resolved configuration used by the rest of the agent."""

    root: Path
    env: Dict[str, str] = field(default_factory=dict)

    # gateway
    provider: str = "openai"
    model: str = "auto"
    routing: Dict[str, Tuple[str, str]] = field(default_factory=dict)
    provider_keys: Dict[str, str] = field(default_factory=dict)
    provider_bases: Dict[str, str] = field(default_factory=dict)

    # limits (0 / none = unlimited)
    max_steps: int = 0
    max_cost_usd: int = 0
    max_context_tokens: int = 0
    rate_per_minute: int = 0

    # autonomy
    autonomy: str = "full"
    allow_self_improve: bool = True
    free_think: bool = True

    # conversation
    conversation_memory: bool = True
    auto_summarize_at_tokens: int = 0

    # language
    languages: List[str] = field(default_factory=lambda: ["en", "hi"])
    default_lang: str = "auto"

    # window / UI
    ui_auto_open: bool = True
    ui_host: str = "127.0.0.1"
    ui_port: int = 0
    ui_title: str = "Agent-Gen"
    graph_view: bool = True

    # second brain
    vault_path: Path = Path("./brain/vault")

    # paths
    brain_dir: Path = field(default_factory=brain_dir)
    memory_path: Path = field(default_factory=lambda: Path("./brain/store/memory.db"))

    @classmethod
    def load(cls, root: Optional[Path] = None) -> "Config":
        root = (root or repo_root()).resolve()
        env = parse_env_file(root / ".env")
        json_data: Dict[str, Any] = {}
        cfg_json = root / "brain" / "config" / "agent.json"
        if cfg_json.exists():
            try:
                json_data = json.loads(cfg_json.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                json_data = {}

        g = json_data.get("gateway", {}) or {}
        limits = json_data.get("limits", {}) or {}
        conv = json_data.get("conversation", {}) or {}
        win = json_data.get("window", {}) or {}
        brain = json_data.get("second_brain", {}) or {}

        def pick(env_key: str, *json_keys: str, default: Any = None) -> Any:
            if env_key in env and env[env_key] != "":
                return env[env_key]
            for jk in json_keys:
                if jk in json_data and json_data[jk] is not None:
                    return json_data[jk]
            return default

        provider = str(pick("AGENT_GEN_PROVIDER", default="openai")).strip() or "openai"
        model = str(pick("AGENT_GEN_MODEL", default="auto")).strip() or "auto"

        # per-capability routing: env AGENT_GEN_MODEL_CHAT="provider/model" wins,
        # else agent.json gateway.routing.<cap>={provider, model}.
        routing: Dict[str, Tuple[str, str]] = {}
        json_routing = g.get("routing", {}) or {}
        for cap in CAPABILITIES:
            env_val = env.get(f"AGENT_GEN_MODEL_{cap.upper()}", "").strip()
            if env_val:
                p, _, m = env_val.partition("/")
                routing[cap] = (p.strip() or provider, m.strip() or model)
                continue
            r = json_routing.get(cap)
            if isinstance(r, dict) and r.get("provider"):
                routing[cap] = (str(r["provider"]), str(r.get("model") or model))
        if "chat" not in routing:
            routing["chat"] = (provider, model)

        # provider keys / base urls
        provider_keys: Dict[str, str] = {}
        for name, env_key in PROVIDER_KEY_ENV.items():
            if env_key:
                value = env.get(env_key, "").strip()
                if value:
                    provider_keys[name] = value
            elif name == "ollama":
                provider_keys[name] = ""  # no key needed

        provider_bases: Dict[str, str] = {}
        for name, base in PROVIDER_BASE_URL.items():
            provider_bases[name] = base
        if env.get("OPENAI_BASE_URL", "").strip():
            provider_bases["openai"] = env["OPENAI_BASE_URL"].strip()
        if env.get("OLLAMA_BASE_URL", "").strip():
            ollama = env["OLLAMA_BASE_URL"].strip()
            # Ollama native URL -> OpenAI-compatible path
            provider_bases["ollama"] = ollama.rstrip("/") + "/v1" if not ollama.endswith("/v1") else ollama
        if env.get("CUSTOM_BASE_URL", "").strip():
            provider_bases["custom"] = env["CUSTOM_BASE_URL"].strip()
        if env.get("AZURE_OPENAI_ENDPOINT", "").strip():
            provider_bases["azure"] = env["AZURE_OPENAI_ENDPOINT"].strip()

        # vault path (env override, else agent.json, else default), relative to root
        vault_rel = str(
            pick("AGENT_GEN_VAULT_PATH", default=str(brain.get("vault_path") or "./brain/vault"))
        )
        vault_path = Path(vault_rel)
        if not vault_path.is_absolute():
            vault_path = root / vault_rel

        brain_path = root / "brain"
        memory_path = root / "brain" / "store" / "memory.db"

        cfg = cls(
            root=root,
            env=env,
            provider=provider,
            model=model,
            routing=routing,
            provider_keys=provider_keys,
            provider_bases=provider_bases,
            max_steps=_to_int(pick("AGENT_GEN_MAX_STEPS", default=limits.get("max_steps", 0))),
            max_cost_usd=_to_int(pick("AGENT_GEN_MAX_COST", default=limits.get("max_cost_usd", 0))),
            max_context_tokens=_to_int(
                pick("AGENT_GEN_MAX_CONTEXT_TOKENS", default=limits.get("max_context_tokens", 0))
            ),
            rate_per_minute=_to_int(
                pick("AGENT_GEN_RATE_LIMIT", default=limits.get("rate_per_minute", 0))
            ),
            autonomy=str(pick("AGENT_GEN_AUTONOMY", default="full")).strip() or "full",
            allow_self_improve=_to_bool(
                pick("AGENT_GEN_ALLOW_SELF_IMPROVE", default=True), True
            ),
            free_think=_to_bool(pick("AGENT_GEN_FREE_THINK", default=True), True),
            conversation_memory=_to_bool(
                pick("AGENT_GEN_CONVERSATION_MEMORY", default=conv.get("persist", True)), True
            ),
            auto_summarize_at_tokens=_to_int(
                pick("AGENT_GEN_AUTO_SUMMARIZE_AT", default=conv.get("auto_summarize_at_tokens", 0))
            ),
            languages=_to_list(pick("AGENT_GEN_LANGUAGES", default=["en", "hi"]), ["en", "hi"]),
            default_lang=str(pick("AGENT_GEN_DEFAULT_LANG", default="auto")).strip() or "auto",
            ui_auto_open=_to_bool(pick("AGENT_GEN_UI_AUTO_OPEN", default=win.get("auto_open", True)), True),
            ui_host=str(env.get("AGENT_GEN_UI_HOST", "") or win.get("host", "127.0.0.1") or "127.0.0.1"),
            ui_port=_to_int(pick("AGENT_GEN_UI_PORT", default=win.get("port", 0))),
            ui_title=str(env.get("AGENT_GEN_UI_TITLE", "") or win.get("title", "Agent-Gen")),
            graph_view=_to_bool(
                pick("AGENT_GEN_GRAPH_VIEW", default=brain.get("graph_view", True)), True
            ),
            vault_path=vault_path,
            brain_dir=brain_path,
            memory_path=memory_path,
        )
        return cfg

    # convenience accessors ------------------------------------------------ #
    def route(self, capability: str) -> Tuple[str, str]:
        return self.routing.get(capability, self.routing.get("chat", (self.provider, self.model)))

    def limit_is_set(self, value: int) -> bool:
        return value is not None and value > 0
