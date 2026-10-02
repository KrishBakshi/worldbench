"""Find and repair judge gaps in scored worlds.

A score is only comparable across models if every model went through the
same pipeline. Two things break that after the fact:

  - **Judge outages.** A judge call that still fails after its retries (a
    provider 503 "high demand", a timeout) leaves an {"error": ...} record.
    A failed WC003/WC004 code probe zeroes its whole biome; a failed visual
    verdict loses the biome's frame half; a failed WC005 probe loses the cycle.
  - **Unrepaired quotes.** Probes now copy code under quote rules and have
    badly copied quotes repaired before grading (eval/quote_repair.py). A
    probe saved before that keeps joined / abbreviated quotes the grader
    rejects, which later worlds would have had repaired.
  - **Unfinished rechecks.** WC003 re-checks every item the frames show but
    the code probe missed. A recheck hunt that errored (an older agent ran
    out of steps every time) or never ran leaves the item at the probe's
    one-shot answer, while other worlds got a working second look.

`find` lists every such gap per world (read-only). `repair` redoes only those
pieces with the pipeline's own functions — the same probes, visual judges,
recheck agent and graders a fresh run would use, on the judge models that
eval/judge.yaml assigns to each job (no model override) — then regrades and
rebuilds the totals (the WC004 island gate is re-applied there). Every other
probe answer, frame and verdict is reused. Each repair is recorded in the
world's validation.json (`details.repairs`), and the files it rewrites are
copied to outputs/<model>/.repair_backups/<UTC time>/ first.

Traced in LangSmith like an eval run: one parent run per world,
`gaps::repair::<model>` (tags: the model, "gaps-repair"; inputs: the gaps
found; outputs: what was done and the before/after scores). Every probe,
recheck hunt (with its LangGraph steps), fallback and quote repair it makes
nests under it, so a repair can be audited as one trace.

Deliberately NOT flagged: a biome the capture never framed. Its visual report
is valid (judged on the wider views) and its motion is "unavailable"; that is
the world's capture result, not a judge outage.

    uv run python -m eval.gaps find                 # every scored world
    uv run python -m eval.gaps find <model> ...
    uv run python -m eval.gaps repair <model> [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langsmith import traceable  # noqa: E402

from eval.loader import load_check  # noqa: E402
from eval.score import score_records  # noqa: E402

OUTPUTS = ROOT / "outputs"
TESTS = ROOT / "tests"
WC003, WC004, WC005 = "WC003_biome_micro_contents", "WC004_biome_rendering", "WC005_day_night_seasons"
KEYS = {
    WC003: f"{WC003}::check_biome_micro_contents",
    WC004: f"{WC004}::check_biome_rendering",
    WC005: f"{WC005}::check_day_night_seasons",
}


def _errored(path: Path) -> list[str]:
    """Keys of a {biome: report} artifact whose report is a judge failure."""
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [k for k, v in data.items() if isinstance(v, dict) and "error" in v]


def _main_module(test: str):
    """The test's main.py module. Every function must come from it: loading
    probe/recheck/visual separately gives each its own copy of the test's
    `llm` module, and isinstance checks across them silently fail."""
    sys.path.insert(0, str(TESTS / test))
    try:
        fn = {WC003: "regrade_micro", WC004: "regrade_rendering", WC005: "regrade_cycle"}[test]
        return sys.modules[load_check(TESTS / test / "main.py", fn).__module__]
    finally:
        sys.path.pop(0)


def _open_rechecks(model: str) -> list[dict]:
    """WC003 items the frames show but the code half rejects, with no
    completed recheck: either never hunted or the hunt errored."""
    D = OUTPUTS / model / WC003
    if not (D / "micro_contents.json").is_file() or not (D / "visual.json").is_file():
        return []
    from eval.capture import judge as visual_io
    from eval.evidence import normalize

    main = _main_module(WC003)
    disagreements = sys.modules[main.recheck.__module__].disagreements
    reports = main.load_reports_from_json(D / "micro_contents.json")
    visual = {k: visual_io.load(v) for k, v in json.loads((D / "visual.json").read_text()).items()}
    source = normalize(main.strip_html(str(OUTPUTS / model / "world.html")))
    done = {}
    if (D / "recheck.json").is_file():
        for h in json.loads((D / "recheck.json").read_text()):
            # a later completed hunt for the same item supersedes an errored one
            if not h.get("error") or (h["biome"], h["item"]) not in done:
                done[(h["biome"], h["item"])] = h
    out = []
    for biome, item, seen in disagreements(reports, visual, tuple(reports), source):
        prior = done.get((biome, item["id"]))
        if prior is None or prior.get("error"):
            out.append({"biome": biome, "item": item["id"], "seen": seen,
                        "why": "errored" if prior else "never_hunted",
                        "detail": (prior or {}).get("error", "")[:120]})
    return out


def _unrepaired_quotes(model: str) -> dict[str, list[str]]:
    """{test: [biome, ...]} whose saved probe quotes the mechanical quote
    repair would still fix — i.e. probes graded without quote repair."""
    from eval.evidence import in_source, normalize
    from eval.quote_repair import _Index, _mechanical, validate

    out: dict[str, list[str]] = {}
    for test, fname in ((WC003, "micro_contents.json"), (WC004, "rendering.json")):
        path = OUTPUTS / model / test / fname
        if not path.is_file():
            continue
        main = _main_module(test)
        src = main.strip_html(str(OUTPUTS / model / "world.html"))
        sn, idx = normalize(src), _Index(src)
        for biome, rep in main.load_reports_from_json(path).items():
            if not hasattr(rep, "model_dump"):
                continue
            # Only quotes the grader rejects and the repair would make pass.
            # validate() also flags "..." — which is valid JS spread syntax
            # (`pond(...p)`) in a quote that already passes; not a gap.
            for f in validate(rep, sn):
                fixed = _mechanical(f.quote, idx)
                if not in_source(f.quote, sn) and fixed and in_source(fixed, sn):
                    out.setdefault(test, []).append(biome)
                    break
    return out


def find(model: str) -> dict:
    """Every judge gap in one world's outputs (no model calls)."""
    O = OUTPUTS / model
    gaps: dict = {
        "WC003_probe": _errored(O / WC003 / "micro_contents.json"),
        "WC003_visual": _errored(O / WC003 / "visual.json"),
        "WC004_probe": _errored(O / WC004 / "rendering.json"),
        "WC004_visual": _errored(O / WC004 / "visual.json"),
        "WC004_motion": _errored(O / WC004 / "motion.json"),
        "WC005_probe": [],
        "WC001_bughunt_views": [],
        "errored_checks": [],
        "WC003_recheck": _open_rechecks(model),
    }
    for test, biomes in _unrepaired_quotes(model).items():
        gaps[f"{test[:5]}_quotes"] = biomes
    cycle = O / WC005 / "cycle.json"
    if cycle.is_file() and "error" in json.loads(cycle.read_text()):
        gaps["WC005_probe"] = ["cycle"]
    bughunt = O / "WC001_voxel_world" / "visual_bughunt_report.json"
    if bughunt.is_file():
        gaps["WC001_bughunt_views"] = [k for k, v in json.loads(bughunt.read_text()).items() if v.get("error")]
    val = O / "validation.json"
    if val.is_file():
        checks = json.loads(val.read_text())["checks"]
        gaps["errored_checks"] = [k for k, c in checks.items() if not c.get("max_score")]
    return {k: v for k, v in gaps.items() if v}


# ── repair ───────────────────────────────────────────────────────────────────


def _backup(model: str, files: list[Path]) -> Path:
    dest = OUTPUTS / model / ".repair_backups" / time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    for f in files:
        if f.is_file():
            target = dest / f.relative_to(OUTPUTS / model)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target)
    return dest


def _update_validation(model: str, test: str, result, note: dict) -> tuple[float, float, float, float]:
    path = OUTPUTS / model / "validation.json"
    v = json.loads(path.read_text())
    key = KEYS[test]
    old = v["checks"].get(key, {})
    before, total_before = old.get("probe_score", old.get("score")), v["total_score"]
    details = dict(result.details)
    details["repairs"] = list((old.get("details") or {}).get("repairs", [])) + [note]
    if test == WC003 and (old.get("details") or {}).get("rechecks"):
        details.setdefault("rechecks", old["details"]["rechecks"])
    # a fresh record: no stale probe_score, so the island gate recomputes from it
    v["checks"][key] = {"passed": result.passed, "reason": result.reason, "details": details,
                        "score": details["score"], "max_score": details["max_score"]}
    v.update(score_records(v["checks"]))
    path.write_text(json.dumps(v, indent=2, default=str))
    return before, v["checks"][key]["score"], total_before, v["total_score"]


def _roles() -> dict:
    from eval.capture.llm import CONFIG

    return dict(CONFIG.get("roles") or {})


@traceable(name="gaps::repair", run_type="chain")
def repair(model: str, dry_run: bool = False) -> list[str]:
    from harness.status import log

    gaps = find(model)
    O = OUTPUTS / model
    html = str(O / "world.html")
    roles = _roles()
    lines: list[str] = []
    if not gaps:
        return [f"{model}: no gaps"]
    if dry_run:
        return [f"{model}: would repair {json.dumps(gaps, default=str)}"]
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # WC003: failed probes, failed visual verdicts, then open rechecks
    if any(k in gaps for k in ("WC003_probe", "WC003_visual", "WC003_recheck", "WC003_quotes")):
        D = O / WC003
        main = _main_module(WC003)
        rc_mod = sys.modules[main.recheck.__module__]
        from eval.capture import judge as visual_io
        from eval.evidence import normalize

        backup = _backup(model, [D / "micro_contents.json", D / "visual.json", D / "score.json",
                                 D / "recheck.json", O / "validation.json"])
        reports = main.load_reports_from_json(D / "micro_contents.json")
        visual = {k: visual_io.load(v) for k, v in json.loads((D / "visual.json").read_text()).items()}
        did: list[str] = []
        if gaps.get("WC003_probe"):
            new = main.probe_all(html, None, tuple(gaps["WC003_probe"]))
            ok = {b: r for b, r in new.items() if not (isinstance(r, dict) and "error" in r)}
            reports.update(ok)
            did.append(f"re-probed {sorted(ok)} (role probe={roles.get('probe')})"
                       + (f"; still failing {sorted(set(new) - set(ok))}" if len(ok) < len(new) else ""))
        if gaps.get("WC003_quotes"):
            from eval.quote_repair import repair_quotes

            src = main.strip_html(html)
            n = sum(len(repair_quotes(reports[b], src, label=b)) for b in gaps["WC003_quotes"]
                    if hasattr(reports[b], "model_dump"))
            did.append(f"quote repair on {gaps['WC003_quotes']} ({n} flagged; role repair={roles.get('repair')})")
        if gaps.get("WC003_visual"):
            vis_mod = sys.modules[main.judge_all.__module__]
            new = vis_mod.judge_all(html, tuple(gaps["WC003_visual"]), None)
            ok = {b: r for b, r in new.items() if not (isinstance(r, dict) and "error" in r)}
            visual.update(ok)
            (D / "visual.json").write_text(json.dumps({k: visual_io.dump(v) for k, v in visual.items()}, indent=2))
            did.append(f"re-judged visuals {sorted(ok)} (role vlm={roles.get('vlm')})")
        # rechecks: re-probed biomes get their normal recheck; open items get one hunt each
        source = normalize(main.strip_html(html))
        targets = {(g["biome"], g["item"]) for g in find(model).get("WC003_recheck", [])}
        reprobed = set(gaps.get("WC003_probe", []))
        hunts = []
        for biome, item, seen in rc_mod.disagreements(reports, visual, tuple(reports), source):
            if (biome, item["id"]) not in targets and biome not in reprobed:
                continue
            req = rc_mod.load_requirements(biome)
            rep = reports[biome]
            aliases = list(dict.fromkeys([*rep.aliases, *req.get("scope_aliases", [])]))
            record = {"biome": biome, "item": item["id"], "seen": seen,
                      "probe": rep.must_present[item["id"]].model_dump() if rep.must_present.get(item["id"]) else None,
                      "repair": stamp}
            try:
                verdict, verified = rc_mod.hunt(html, biome=req.get("label", biome), aliases=aliases,
                                                feature=item.get("label", item["id"]), visual_hint=seen, model=None)
            except Exception as exc:  # a failed hunt leaves the probe's answer standing
                hunts.append({**record, "error": str(exc)[:300]})
                continue
            record.update(agent=verdict.model_dump(), verified=verified)
            if verified:
                rep.must_present[item["id"]] = rc_mod.ItemJudgement(found=True, evidence=verdict.evidence)
            hunts.append(record)
        if hunts:
            old = json.loads((D / "recheck.json").read_text()) if (D / "recheck.json").is_file() else []
            (D / "recheck.json").write_text(json.dumps(old + hunts, indent=2))
            did.append(f"{len(hunts)} recheck hunt(s), {sum(1 for h in hunts if h.get('verified'))} verified "
                       f"(role judge={roles.get('judge')})")
        (D / "micro_contents.json").write_text(json.dumps(
            {b: (r.model_dump() if hasattr(r, "model_dump") else r) for b, r in reports.items()}, indent=2))
        result = main.regrade_micro(D / "micro_contents.json")
        note = {"at": stamp, "did": did, "backup": str(backup.relative_to(O))}
        b, a, tb, ta = _update_validation(model, WC003, result, note)
        lines.append(f"{model} WC003: {'; '.join(did)} | {b} -> {a} | total {tb} -> {ta}")
        log(f"      gaps      {lines[-1]}")

    # WC004: failed probes and failed visual / motion verdicts
    if any(k in gaps for k in ("WC004_probe", "WC004_visual", "WC004_motion", "WC004_quotes")):
        D = O / WC004
        main = _main_module(WC004)
        vis_mod = sys.modules[main.judge_all.__module__]
        from eval.capture import judge as visual_io

        backup = _backup(model, [D / "rendering.json", D / "visual.json", D / "motion.json",
                                 D / "score.json", O / "validation.json"])
        did = []
        reports = main.load_reports_from_json(D / "rendering.json")
        if gaps.get("WC004_probe"):
            new = main.probe_all(html, None, tuple(gaps["WC004_probe"]))
            ok = {b: r for b, r in new.items() if not (isinstance(r, dict) and "error" in r)}
            reports.update(ok)
            (D / "rendering.json").write_text(json.dumps(
                {b: (r.model_dump() if hasattr(r, "model_dump") else r) for b, r in reports.items()}, indent=2))
            did.append(f"re-probed {sorted(ok)} (role probe={roles.get('probe')})")
        if gaps.get("WC004_quotes"):
            from eval.quote_repair import repair_quotes

            src = main.strip_html(html)
            n = sum(len(repair_quotes(reports[b], src, label=b)) for b in gaps["WC004_quotes"]
                    if hasattr(reports[b], "model_dump"))
            (D / "rendering.json").write_text(json.dumps(
                {b: (r.model_dump() if hasattr(r, "model_dump") else r) for b, r in reports.items()}, indent=2))
            did.append(f"quote repair on {gaps['WC004_quotes']} ({n} flagged; role repair={roles.get('repair')})")
        redo = tuple(sorted(set(gaps.get("WC004_visual", [])) | set(gaps.get("WC004_motion", []))))
        if redo:
            looks, motions = vis_mod.judge_all(html, redo, None)
            visual = json.loads((D / "visual.json").read_text())
            motion = json.loads((D / "motion.json").read_text()) if (D / "motion.json").is_file() else {}
            for b in redo:
                if not (isinstance(looks.get(b), dict) and "error" in looks[b]):
                    visual[b] = visual_io.dump(looks[b])
                if b in motions and not (isinstance(motions[b], dict) and "error" in motions[b]):
                    motion[b] = vis_mod.dump_motion(motions[b])
            (D / "visual.json").write_text(json.dumps(visual, indent=2))
            (D / "motion.json").write_text(json.dumps(motion, indent=2))
            did.append(f"re-judged visuals/motion {list(redo)} (role vlm={roles.get('vlm')})")
        result = main.regrade_rendering(D / "rendering.json")
        note = {"at": stamp, "did": did, "backup": str(backup.relative_to(O))}
        b, a, tb, ta = _update_validation(model, WC004, result, note)
        lines.append(f"{model} WC004: {'; '.join(did)} | {b} -> {a} (before island gate) | total {tb} -> {ta}")
        log(f"      gaps      {lines[-1]}")

    # WC005: a failed cycle probe
    if gaps.get("WC005_probe"):
        D = O / WC005
        main = _main_module(WC005)
        probe_mod = sys.modules[main.probe_cycle.__module__]
        backup = _backup(model, [D / "cycle.json", D / "score.json", O / "validation.json"])
        report = probe_mod.probe_cycle(html, None)
        (D / "cycle.json").write_text(json.dumps(report.model_dump(), indent=2))
        result = main.regrade_cycle(D / "cycle.json")
        note = {"at": stamp, "did": [f"re-probed cycle (role probe={roles.get('probe')})"], "backup": str(backup.relative_to(O))}
        b, a, tb, ta = _update_validation(model, WC005, result, note)
        lines.append(f"{model} WC005: re-probed cycle | {b} -> {a} | total {tb} -> {ta}")

    for k in ("WC001_bughunt_views", "errored_checks"):
        if gaps.get(k):
            lines.append(f"{model}: {k} {gaps[k]} need a full re-run of that test (eval.run --test ...)")
    return lines


def _worlds(names: list[str]) -> list[str]:
    if names:
        return names
    return sorted(p.parent.name for p in OUTPUTS.glob("*/validation.json"))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Find / repair judge gaps in scored worlds")
    sub = parser.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("find", help="list judge outages and unfinished rechecks (no model calls)")
    f.add_argument("models", nargs="*")
    r = sub.add_parser("repair", help="redo only the gaps with the pipeline's own judges")
    r.add_argument("models", nargs="+")
    r.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.cmd == "find":
        for m in _worlds(args.models):
            gaps = find(m)
            total = json.loads((OUTPUTS / m / "validation.json").read_text())["total_score"]
            print(f"{m:20} {total:7.2f}  {'clean' if not gaps else ''}")
            for k, v in gaps.items():
                items = [f"{g['biome']}/{g['item']} ({g['why']})" for g in v] if k == "WC003_recheck" else v
                print(f"    {k:20} {items}")
    else:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
        for m in args.models:
            extra = {"name": f"gaps::repair::{m}", "tags": [m, "gaps-repair"] + (["dry-run"] if args.dry_run else []),
                     "metadata": {"model": m, "kind": "gaps-repair", "dry_run": args.dry_run, "roles": _roles()}}
            for line in repair(m, dry_run=args.dry_run, langsmith_extra=extra):
                print(line)


if __name__ == "__main__":
    main()
