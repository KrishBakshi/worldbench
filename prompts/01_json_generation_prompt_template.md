# Stage 1 — Generate a world.json (the assembly recipe)

Unlike stage 2 (`02_html_generation_prompt_template.md`), stage 1 has no
single prompt that works for every task — the world being asked for is
different per task, so the prompt text is different per task. What *is*
constant is the recipe every task's stage-1 prompt is assembled from. This
file documents that recipe and points to a ready-made example.

## The recipe

A task's stage-1 prompt is always these four pieces, concatenated in this
order:

1. **System prompt** — from that task's own `task.yaml` → `system_prompt` field.
2. **User prompt** — that task's own `prompt.md`.
3. **Constraints** — that task's own `constraints.yaml` (if it has one).
4. **JSON Schema** — `benchmark/schemas/world_schema_v1.json`, verbatim. This
   piece is the same for every task; it's what tells a chat website the exact
   field names/types/enums it has no other way of knowing.

Ask the model to output ONLY the JSON object — no prose, no code fences —
then save the reply as `manual_generation/output/<model_name>/world.json`.

## Ready-made example

Every task that supports manual (no-API) generation already has this
assembled for you — you don't need to build it by hand. See:

```
prompts/08_world_composition/WC001_complete_floating_world/01_generate_json_prompt.md
```

That file is exactly the four pieces above, pre-assembled and ready to paste
as-is into any LLM chat website.

## Building one for a different task

To do this for another task (e.g. `prompts/01_world_layout/WL001_layout_floating_archipelago/`),
concatenate that task's own `task.yaml` system prompt + `prompt.md` +
`constraints.yaml` (if present) + `benchmark/schemas/world_schema_v1.json`, in
that order, following the exact format in the WC001 example above.

## Then stage 2

Once you have a `world.json`, move on to
`prompts/02_html_generation_prompt_template.md` to generate the companion
`world.html`. See `manual_generation/README.md` for the full walkthrough of
both stages, and `worldbench evaluate <model_dir>` to score both files at once.
