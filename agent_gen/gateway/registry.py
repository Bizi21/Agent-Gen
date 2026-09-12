"""Adapter registry: build an LLM for a capability from config.

Any provider without a key (or with an unknown name) gracefully falls back
to :class:`MockLLM`, so the agent always runs — offline included.
"""

from __future__ import annotations

import sys
from typing import Dict, Tuple

from ..config import CAPABILITIES, Config
from .anthropic import AnthropicLLM
from .base import LLM
from .google import GoogleLLM
from .mock import MockLLM
from .openai_compat import OpenAICompatLLM

# OpenAI-compatible providers that need a key.
KEYED_COMPAT = {"openai", "mistral", "groq", "deepseek", "together", "openrouter", "cohere"}


def build_llm(provider: str, model: str, config: Config) -> LLM:
    """Build a single LLM adapter for ``provider`` / ``model``, or a mock."""
    provider = (provider or config.provider).strip().lower()
    model = (model or config.model or "auto").strip()
    if model == "auto":
        model = _auto_model(provider, config)

    key = config.provider_keys.get(provider, "")
    base = config.provider_bases.get(provider, "")

    if provider == "anthropic":
        if key:
            return AnthropicLLM(api_key=key, model=model)
        return _fallback(provider, "no ANTHROPIC_API_KEY")

    if provider == "google":
        if key:
            return GoogleLLM(api_key=key, model=model)
        return _fallback(provider, "no GOOGLE_API_KEY")

    if provider in KEYED_COMPAT:
        if key and base:
            return OpenAICompatLLM(base_url=base, api_key=key, model=model)
        return _fallback(provider, f"no key/base_url (set the key in .env)")

    if provider == "ollama":
        # Ollama is local; no key needed.
        return OpenAICompatLLM(base_url=base, api_key="", model=model, capabilities=frozenset({"chat"}))

    if provider == "custom":
        if base:
            return OpenAICompatLLM(base_url=base, api_key=key, model=model)
        return _fallback(provider, "no CUSTOM_BASE_URL")

    if provider == "azure":
        return _fallback(provider, "Azure adapter not implemented yet; use CUSTOM_BASE_URL")

    return _fallback(provider, "unknown provider")


def _auto_model(provider: str, config: Config) -> str:
    defaults = {
        "openai": "gpt-4o-mini",
        "anthropic": "claude-3-5-haiku-latest",
        "google": "gemini-1.5-flash",
        "mistral": "mistral-small-latest",
        "groq": "llama-3.1-8b-instant",
        "deepseek": "deepseek-chat",
        "together": "meta-llama/Llama-3.1-8B-Instruct",
        "openrouter": "openai/gpt-4o-mini",
        "cohere": "command-r",
        "ollama": config.env.get("OLLAMA_MODEL", "") or "llama3.1",
        "custom": config.env.get("CUSTOM_MODEL", "") or "local-model",
    }
    return defaults.get(provider, "auto")


def _fallback(provider: str, reason: str) -> MockLLM:
    print(f"[gateway] provider '{provider}' unavailable ({reason}) -> using offline mock LLM",
          file=sys.stderr)
    return MockLLM()


def resolve_llm(capability: str, config: Config) -> LLM:
    """Resolve the LLM for a capability, with a small cache per config."""
    if capability not in CAPABILITIES:
        capability = "chat"
    provider, model = config.route(capability)
    return build_llm(provider, model, config)


class LLMPool:
    """Lazily-built pool of capability -> LLM adapters."""

    def __init__(self, config: Config):
        self.config = config
        self._cache: Dict[str, LLM] = {}

    def get(self, capability: str = "chat") -> LLM:
        if capability not in self._cache:
            self._cache[capability] = resolve_llm(capability, self.config)
        return self._cache[capability]
