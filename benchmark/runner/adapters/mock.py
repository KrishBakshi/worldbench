"""A deterministic offline adapter for tests, demos, and CI.

The mock adapter never touches the network. It returns a pre-baked, fully valid
WorldBench world so the entire pipeline (parse → validate → score → report) can
be exercised reproducibly. The returned world is generated from
:func:`benchmark.samples.sample_world`, keeping a single canonical example in
one place.
"""

from __future__ import annotations

from .base import GenerationConfig, ModelAdapter


class MockAdapter(ModelAdapter):
    """Returns a canonical valid world regardless of the prompt."""

    name = "mock"

    def __init__(self, config: GenerationConfig | None = None):
        super().__init__(config or GenerationConfig(model="mock-world-1"))

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        # Imported lazily so the samples module (which imports models) is only
        # loaded when the mock adapter is actually used.
        from ...samples import sample_world

        return sample_world().to_json()
