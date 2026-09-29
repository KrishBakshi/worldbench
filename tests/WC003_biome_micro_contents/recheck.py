"""Second look at code-vs-frames disagreements, with the evidence agent.

The one-shot probe (probe.py) answers every item of a biome from a single
read of the source. When the frames show an item that the probe's code half
rejected, that's the case a single read gets wrong most: a feature built
implicitly (terraced noise, a height-band colour) with no identifier naming
it. Only those items get the agent (eval/evidence_agent.py) — agreement,
and anything the frames didn't show, is left exactly as the probe said.

A confirmed hunt replaces the item's judgement with the agent's verbatim
evidence, which grade.py then checks like any other quote (in the source,
not a comment/legend/bare token). Every hunt, confirmed or not, is recorded
in recheck.json beside the other artifacts.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from grade import _presence
from llm import BiomeMicroReport, ItemJudgement, load_requirements

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.append(str(_ROOT))
from eval.capture.judge import VisualReport  # noqa: E402
from eval.evidence_agent import hunt  # noqa: E402
from harness.status import log  # noqa: E402
from eval.capture.llm import JudgeUnavailable  # noqa: E402


def disagreements(reports: dict, visual: dict, biome_ids: tuple[str, ...], source_normalized: str) -> list[tuple[str, dict, str]]:
    """(biome_id, requirement item, what the frames showed) for every
    must_present item the frames saw but the code half rejected."""
    out = []
    for biome_id in biome_ids:
        report, seen = reports.get(biome_id), visual.get(biome_id)
        if not isinstance(report, BiomeMicroReport) or not isinstance(seen, VisualReport):
            continue
        sightings = {s.id: s for s in seen.items}
        for item in load_requirements(biome_id).get("must_present", []):
            sighting = sightings.get(item["id"])
            if not (sighting and sighting.visible):
                continue
            code_ok, _ = _presence(report.must_present.get(item["id"]), source_normalized)
            if not code_ok:
                out.append((biome_id, item, sighting.seen))
    return out


def recheck(
    html_path: str,
    reports: dict,
    visual: dict,
    biome_ids: tuple[str, ...],
    source_normalized: str,
    model: str | None = None,
) -> list[dict]:
    """Hunt every disagreement; patch confirmed ones into `reports` in place.
    Returns one record per hunt for recheck.json."""
    todo = disagreements(reports, visual, biome_ids, source_normalized)
    if not todo:
        log("      recheck  no code/frames disagreements")
        return []
    log(f"      recheck  {len(todo)} item(s) the frames show but the code probe missed")
    records = []
    for biome_id, item, seen in todo:
        req = load_requirements(biome_id)
        report: BiomeMicroReport = reports[biome_id]
        aliases = list(dict.fromkeys([*report.aliases, *req.get("scope_aliases", [])]))
        before = report.must_present.get(item["id"])
        record = {"biome": biome_id, "item": item["id"], "seen": seen, "probe": before.model_dump() if before else None}
        try:
            verdict, verified = hunt(
                html_path,
                biome=req.get("label", biome_id),
                aliases=aliases,
                feature=item.get("label", item["id"]),
                visual_hint=seen,
                model=model,
            )
        except JudgeUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 — a failed hunt leaves the probe's answer standing
            log(f"      recheck  {biome_id}/{item['id']}  error: {exc}")
            records.append({**record, "error": str(exc)})
            continue
        record.update(agent=verdict.model_dump(), verified=verified)
        if verified:
            report.must_present[item["id"]] = ItemJudgement(found=True, evidence=verdict.evidence)
        records.append(record)
    return records
