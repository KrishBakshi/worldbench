"""Google Gemini (Generative Language API) adapter."""

from __future__ import annotations

import httpx

from .base import AdapterError, GenerationConfig, ModelAdapter


class GeminiAdapter(ModelAdapter):
    """Calls the Gemini ``generateContent`` REST endpoint.

    Configuration (environment variables):

    * ``GEMINI_API_KEY`` (or ``GOOGLE_API_KEY``) — required.
    * ``GEMINI_BASE_URL`` — defaults to
      ``https://generativelanguage.googleapis.com/v1beta``.
    * ``GEMINI_MODEL`` — default model when none is passed explicitly.
    """

    name = "gemini"
    default_base_url = "https://generativelanguage.googleapis.com/v1beta"
    default_model = "gemini-1.5-pro"

    def __init__(self, config: GenerationConfig | None = None):
        model = (config.model if config else None) or self._env(
            "GEMINI_MODEL", default=self.default_model
        )
        super().__init__(config or GenerationConfig(model=model))
        self.config.model = model
        self.base_url = (self._env("GEMINI_BASE_URL", default=self.default_base_url) or "").rstrip("/")
        self.api_key = self._env("GEMINI_API_KEY", "GOOGLE_API_KEY")

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        if not self.api_key:
            raise AdapterError(f"{self.name}: GEMINI_API_KEY is not set")
        payload: dict = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": self.config.temperature,
                "maxOutputTokens": self.config.max_tokens,
            },
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        url = f"{self.base_url}/models/{self.config.model}:generateContent"
        try:
            resp = httpx.post(
                url,
                params={"key": self.api_key},
                headers={"Content-Type": "application/json", **self.config.extra_headers},
                json=payload,
                timeout=self.config.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(part.get("text", "") for part in parts)
        except httpx.HTTPError as exc:  # pragma: no cover - network path
            raise AdapterError(f"{self.name} request failed: {exc}") from exc
        except (KeyError, IndexError) as exc:  # pragma: no cover - malformed
            raise AdapterError(f"{self.name} returned an unexpected response shape: {exc}") from exc
