"""vLLM adapter — reuses the OpenAI-compatible server vLLM exposes.

A vLLM ``--api-server`` speaks the OpenAI Chat Completions protocol, so this
adapter only overrides configuration defaults (base URL, optional key) and
inherits request/response handling from :class:`OpenAIAdapter`.

Configuration (environment variables):

* ``VLLM_BASE_URL`` — defaults to ``http://localhost:8000/v1``.
* ``VLLM_MODEL`` — model name registered with the vLLM server.
* ``VLLM_API_KEY`` — optional; many local deployments need none.
"""

from __future__ import annotations

from .base import GenerationConfig
from .openai import OpenAIAdapter


class VLLMAdapter(OpenAIAdapter):
    name = "vllm"
    default_base_url = "http://localhost:8000/v1"
    default_model = "meta-llama/Llama-3.1-8B-Instruct"

    def __init__(self, config: GenerationConfig | None = None):
        model = (config.model if config else None) or self._env(
            "VLLM_MODEL", default=self.default_model
        )
        # Skip OpenAIAdapter's OPENAI_* env wiring; go straight to the base
        # constructor and configure vLLM's own environment variables.
        super(OpenAIAdapter, self).__init__(config or GenerationConfig(model=model))
        self.config.model = model
        self.base_url = (self._env("VLLM_BASE_URL", default=self.default_base_url) or "").rstrip("/")
        # vLLM often runs open; a placeholder keeps the Authorization header valid.
        self.api_key = self._env("VLLM_API_KEY", default="EMPTY")
