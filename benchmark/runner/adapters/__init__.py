"""Model adapters and the adapter registry.

Every provider is registered by name so the runner and CLI can instantiate one
from a single ``--adapter <name>`` flag. Adding a provider is a two-line change:
implement :class:`ModelAdapter` and add it to ``_REGISTRY``.
"""

from __future__ import annotations

from .anthropic import AnthropicAdapter
from .base import AdapterError, GenerationConfig, ModelAdapter
from .gemini import GeminiAdapter
from .mock import MockAdapter
from .ollama import OllamaAdapter
from .openai import OpenAIAdapter
from .vllm import VLLMAdapter

_REGISTRY: dict[str, type[ModelAdapter]] = {
    MockAdapter.name: MockAdapter,
    OpenAIAdapter.name: OpenAIAdapter,
    AnthropicAdapter.name: AnthropicAdapter,
    GeminiAdapter.name: GeminiAdapter,
    OllamaAdapter.name: OllamaAdapter,
    VLLMAdapter.name: VLLMAdapter,
}


def available_adapters() -> list[str]:
    """Return the registered adapter names."""
    return sorted(_REGISTRY)


def get_adapter(name: str, config: GenerationConfig | None = None) -> ModelAdapter:
    """Instantiate a registered adapter by name.

    Raises :class:`AdapterError` for an unknown name so the CLI can surface a
    clear message listing valid choices.
    """
    try:
        cls = _REGISTRY[name]
    except KeyError as exc:
        raise AdapterError(
            f"unknown adapter {name!r}; choose from: {', '.join(available_adapters())}"
        ) from exc
    return cls(config)


__all__ = [
    "AdapterError",
    "GenerationConfig",
    "ModelAdapter",
    "MockAdapter",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "GeminiAdapter",
    "OllamaAdapter",
    "VLLMAdapter",
    "available_adapters",
    "get_adapter",
]
