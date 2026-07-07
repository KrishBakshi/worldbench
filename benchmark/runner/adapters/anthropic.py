"""Anthropic Messages API adapter."""

from __future__ import annotations

import httpx

from .base import AdapterError, GenerationConfig, ModelAdapter


class AnthropicAdapter(ModelAdapter):
    """Calls the Anthropic ``/v1/messages`` endpoint.

    Configuration (environment variables):

    * ``ANTHROPIC_API_KEY`` — required.
    * ``ANTHROPIC_BASE_URL`` — defaults to ``https://api.anthropic.com``.
    * ``ANTHROPIC_MODEL`` — default model when none is passed explicitly.
    * ``ANTHROPIC_VERSION`` — API version header, defaults to ``2023-06-01``.
    """

    name = "anthropic"
    default_base_url = "https://api.anthropic.com"
    default_model = "claude-sonnet-4-5"
    default_version = "2023-06-01"

    def __init__(self, config: GenerationConfig | None = None):
        model = (config.model if config else None) or self._env(
            "ANTHROPIC_MODEL", default=self.default_model
        )
        super().__init__(config or GenerationConfig(model=model))
        self.config.model = model
        self.base_url = (self._env("ANTHROPIC_BASE_URL", default=self.default_base_url) or "").rstrip("/")
        self.api_key = self._env("ANTHROPIC_API_KEY")
        self.version = self._env("ANTHROPIC_VERSION", default=self.default_version)

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise AdapterError(f"{self.name}: ANTHROPIC_API_KEY is not set")
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.version or self.default_version,
            "Content-Type": "application/json",
        }
        headers.update(self.config.extra_headers)
        return headers

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        payload: dict = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        try:
            resp = httpx.post(
                f"{self.base_url}/v1/messages",
                headers=self._headers(),
                json=payload,
                timeout=self.config.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            # Content is a list of blocks; concatenate the text blocks.
            return "".join(
                block.get("text", "")
                for block in data.get("content", [])
                if block.get("type") == "text"
            )
        except httpx.HTTPError as exc:  # pragma: no cover - network path
            raise AdapterError(f"{self.name} request failed: {exc}") from exc
        except (KeyError, TypeError) as exc:  # pragma: no cover - malformed
            raise AdapterError(f"{self.name} returned an unexpected response shape: {exc}") from exc
