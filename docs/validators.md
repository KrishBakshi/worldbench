# WorldBench Validator Reference

Validators are deterministic checks that enforce the natural laws a believable
world must obey. Each lives in `benchmark/validators/`, exposes
`validate(world) -> ValidationResult`, and emits typed `Finding`s carrying a
`code` (a three-letter prefix + number), a `severity`, a `message`, and
optionally the `entity_id`/`path` concerned.

## Severity semantics

| Severity  | Meaning                                                                    |
|-----------|----------------------------------------------------------------------------|
| `error`   | A broken natural law or referential-integrity failure. Fails the validator |
| `warning` | Implausible but not impossible (natural transitions are sometimes abrupt)   |
| `info`    | Neutral observation                                                        |

A `ValidationResult.passed` is `True` when it raised **no `error` findings**.
`pass_rate` is `checks_passed / checks_run`.

## The validators

| Validator      | Prefix | Checks (errors unless noted)                                                                 |
|----------------|:------:|----------------------------------------------------------------------------------------------|
| schema         | `SCH`  | The world parses against the JSON Schema/Pydantic models; `metadata.schema_version` matches. Exposes `validate_dict` to check raw LLM JSON before it becomes a `World`. |
| topology       | `TOP`  | All coordinates/footprints inside `layout.bounds`; region adjacency is symmetric; floating topologies use `void`/`cliff` edges; terrain `connected_to` and region refs resolve. |
| hydrology      | `HYD`  | `flows_to`/`source_ids` resolve; flowing bodies terminate (terminal body or `exits_world`); no flow cycles; water never flows uphill; knowledge `may_flow_to` compliance (warning). |
| biome          | `BIO`  | Biome temperature/moisture satisfy knowledge `requires`; adjacency symmetric and plausible (`may_be_adjacent`, warnings); referenced terrain/water ids resolve. |
| flora          | `FLO`  | Every `biome_ids` resolves; each host biome `supports_flora` the category; insect/bird/bat pollination has a matching pollinator (warning). |
| fauna          | `FAU`  | `biome_ids` resolve and `supports_fauna` the category; diet ids resolve; herbivores/omnivores have flora in diet; carnivores/omnivores/apex have prey; locomotion vs habitat sanity (warning). |
| ecology        | `ECO`  | The `food_web` is acyclic; every carnivore has reachable prey; at least one producer feeds the web; trophic depth ≥ 2 (warning if trivially shallow); isolated species flagged (warning). |
| interaction    | `INT`  | Interaction `source_id`/`target_id` resolve; endpoints match the interaction type (predation fauna→fauna, pollination fauna→flora/biome, migration fauna→biome/region); duplicate edges (warning). |
| constraint     | `CON`  | **Scope enforcement** — scans names/descriptions/tags for civilization terms (city, village, road, building, farm, human, …) and rejects them. Also enforces optional task constraints (`min_biomes`, `required_biome_types`, `forbidden_terms`, …). |
| weather        | `WEA`  | Every biome has a `biome_weather` entry; precipitation/`annual_precipitation` consistency; snow only in cold/polar biomes (warning); wind ids resolve. |
| simulation     | `SIM`  | Every dynamic's `involves_ids` resolve; a `predator_prey_cycle` references a real predation pair; migration dynamics reference migratory fauna/interactions. |

## The composite: `validate_world`

`benchmark/validators/composite.py` exposes:

```python
from benchmark.validators import validate_world

report = validate_world(world, constraints=None)   # -> ValidationReport
report.passed          # True iff no validator raised an error
report.error_count()   # total error findings across all validators
report.warning_count() # total warnings
report.all_findings    # flattened list of every Finding
```

It runs all validators in a fixed order (registered in the `VALIDATORS` list) and
aggregates their `ValidationResult`s into a single `ValidationReport`. The
optional `constraints` dict — typically loaded from a task's `constraints.yaml`
— is passed to the constraint validator so per-task requirements are enforced
alongside the universal ones.

## The report shape

```
ValidationReport
├── results: list[ValidationResult]
│   └── ValidationResult
│       ├── validator: str            # e.g. "hydrology"
│       ├── passed: bool
│       ├── findings: list[Finding]   # each with code / severity / message / entity_id
│       ├── checks_run: int
│       └── checks_passed: int
├── .passed          (property)
├── .all_findings    (property)
├── .error_count()
└── .warning_count()
```

These types are defined in `benchmark/results.py` and shared with the metrics
layer, which can reuse a report's pass-rates when scoring.
