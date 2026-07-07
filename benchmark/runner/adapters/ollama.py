"""Ollama local-inference adapter."""

from __future__ import annotations

import httpx

from .base import AdapterError, GenerationConfig, ModelAdapter


class OllamaAdapter(ModelAdapter):
    """Calls a local Ollama server's ``/api/chat`` endpoint.

    Configuration (environment variables):

    * ``OLLAMA_HOST`` — defaults to ``http://localhost:11434``.
    * ``OLLAMA_MODEL`` — default model when none is passed explicitly.

    No API key is required; Ollama runs locally.
    """

    name = "ollama"
    default_host = "http://localhost:11434"
    default_model = "llama3.1"

    def __init__(self, config: GenerationConfig | None = None):
        model = (config.model if config else None) or self._env(
            "OLLAMA_MODEL", default=self.default_model
        )
        super().__init__(config or GenerationConfig(model=model))
        self.config.model = model
        self.host = (self._env("OLLAMA_HOST", default=self.default_host) or "").rstrip("/")

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            },
        }
        try:
            resp = httpx.post(
                f"{self.host}/api/chat",
                headers={"Content-Type": "application/json", **self.config.extra_headers},
                json=payload,
                timeout=self.config.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"]
        except httpx.HTTPError as exc:  # pragma: no cover - network path
            raise AdapterError(f"{self.name} request failed: {exc}") from exc
        except (KeyError, TypeError) as exc:  # pragma: no cover - malformed
            raise AdapterError(f"{self.name} returned an unexpected response shape: {exc}") from exc
