"""OpenAI Chat Completions adapter (also the base for vLLM's compatible API)."""

from __future__ import annotations

import httpx

from .base import AdapterError, GenerationConfig, ModelAdapter


class OpenAIAdapter(ModelAdapter):
    """Calls an OpenAI-compatible ``/chat/completions`` endpoint.

    Configuration (environment variables):

    * ``OPENAI_API_KEY`` — required bearer token.
    * ``OPENAI_BASE_URL`` — defaults to ``https://api.openai.com/v1``.
    * ``OPENAI_MODEL`` — default model when none is passed explicitly.
    """

    name = "openai"
    default_base_url = "https://api.openai.com/v1"
    default_model = "gpt-4o"

    def __init__(self, config: GenerationConfig | None = None):
        model = (config.model if config else None) or self._env(
            "OPENAI_MODEL", default=self.default_model
        )
        super().__init__(config or GenerationConfig(model=model))
        if config is None:
            self.config.model = model
        self.base_url = (self._env("OPENAI_BASE_URL", default=self.default_base_url) or "").rstrip("/")
        self.api_key = self._env("OPENAI_API_KEY")

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise AdapterError(f"{self.name}: OPENAI_API_KEY is not set")
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        headers.update(self.config.extra_headers)
        return headers

    def _payload(self, prompt: str, system: str | None) -> dict:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        try:
            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=self._payload(prompt, system),
                timeout=self.config.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except httpx.HTTPError as exc:  # pragma: no cover - network path
            raise AdapterError(f"{self.name} request failed: {exc}") from exc
        except (KeyError, IndexError) as exc:  # pragma: no cover - malformed
            raise AdapterError(f"{self.name} returned an unexpected response shape: {exc}") from exc
