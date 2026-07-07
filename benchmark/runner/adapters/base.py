"""The model-adapter interface every provider implements.

A :class:`ModelAdapter` turns a text prompt into raw model output (expected to
be a JSON world document). Adapters are intentionally thin: they handle
transport, authentication, and request shaping only. Parsing, validation, and
scoring happen downstream in the runner, so a broken or non-JSON response is a
*data* problem the benchmark measures, not an adapter error to hide.

All adapters read their configuration (API key, base URL, model id) from
environment variables with sane defaults, so the runner can construct any of
them from a single ``--adapter <name>`` flag without provider-specific plumbing.
"""

from __future__ import annotations

import abc
import os
from dataclasses import dataclass, field


@dataclass
class GenerationConfig:
    """Sampling and transport settings shared across adapters."""

    model: str
    temperature: float = 0.7
    max_tokens: int = 8192
    timeout: float = 120.0
    extra_headers: dict[str, str] = field(default_factory=dict)


class AdapterError(RuntimeError):
    """Raised when an adapter cannot obtain a response from its provider."""


class ModelAdapter(abc.ABC):
    """Abstract base for all model providers.

    Subclasses implement :meth:`generate`, returning the raw text the model
    produced. The runner is responsible for extracting JSON from that text.
    """

    #: Registry name used by ``--adapter <name>``.
    name: str = "base"

    def __init__(self, config: GenerationConfig):
        self.config = config

    @abc.abstractmethod
    def generate(self, prompt: str, *, system: str | None = None) -> str:
        """Return the model's raw text response to ``prompt``.

        ``system`` is an optional system/instruction message. Implementations
        should raise :class:`AdapterError` on transport or auth failure.
        """

    # -- shared helpers --------------------------------------------------
    @staticmethod
    def _env(*names: str, default: str | None = None) -> str | None:
        """Return the first set environment variable among ``names``."""
        for n in names:
            value = os.environ.get(n)
            if value:
                return value
        return default

    def describe(self) -> dict[str, str]:
        """Human/report-friendly description of this adapter instance."""
        return {"adapter": self.name, "model": self.config.model}
