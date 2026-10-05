from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from llm import CheckResult, ExtractedGraph

# Per biome: 1 point for being covered at all, 1 for correct placement.
# An uncovered biome scores 0/2 and is drawn as "not covered", not as a fail.
COVERAGE_POINTS = 1
PLACEMENT_POINTS = 1
POINTS_PER_BIOME = COVERAGE_POINTS + PLACEMENT_POINTS

RULES = {
    "mountains": {"must_connect": ["forest"], "higher_than": ["forest", "highlands", "jungle", "grassland", "delta"]},
    "forest": {"must_connect": ["mountains", "highlands"], "higher_than": ["highlands", "jungle", "grassland", "delta"]},
    "highlands": {"must_connect": ["forest", "jungle"], "higher_than": ["jungle", "grassland", "delta"]},
    "jungle": {"must_connect": ["highlands", "grassland", "swamp"], "higher_than": ["grassland", "delta"]},
    "swamp": {"must_connect": ["jungle"], "must_not_connect": ["delta"]},
    "grove": {"must_connect_any": ["highlands", "grassland"]},
    "grassland": {"must_connect": ["jungle", "delta"], "higher_than": ["delta"]},
    "delta": {"must_connect": ["grassland"]},
    "desert": {"must_not_connect": ["mountains", "forest", "highlands", "jungle", "delta"]},
    "volcano": {"must_not_connect": ["mountains", "forest", "highlands", "grassland", "delta"]},
}


def grade_graph(graph: ExtractedGraph, covered: dict[str, bool] | None = None) -> CheckResult:
    """`covered` comes from coverage.py; None treats every biome as covered
    (grading a hand-built graph on its own)."""
    covered = covered or {bid: True for bid in RULES}
    adj: dict[str, set[str]] = defaultdict(set)
    for node in graph.nodes:
        if not covered.get(node.id):
            continue  # an uncovered biome has no real layout to touch anything
        for n in node.neighbors:
            if not covered.get(n):
                continue
            adj[node.id].add(n)
            adj[n].add(node.id)
    rank = {b: i for i, b in enumerate(graph.elevation_order)}
    evidence = {n.id: n.evidence for n in graph.nodes}

    found, missing = {}, {}
    biomes = {}
    for bid, rules in RULES.items():
        if not covered.get(bid):
            card = _uncovered(bid)
        else:
            card = _grade_one(bid, rules, adj, rank, evidence.get(bid, "not in source"), covered)
        biomes[bid] = card
        (found if card["passed"] else missing)[bid] = card["summary"]

    score = sum(card["score"] for card in biomes.values())
    max_score = POINTS_PER_BIOME * len(RULES)
    uncovered = [bid for bid in RULES if not covered.get(bid)]
    passed = not missing
    reason = (
        "All biomes covered and correctly placed"
        if passed
        else f"Scored {score}/{max_score}; not covered: {', '.join(uncovered) or 'none'}; "
        f"misplaced: {', '.join(b for b in missing if b not in uncovered) or 'none'}"
    )
    scorecard = {
        "score": score,
        "max_score": max_score,
        "points_per_biome": POINTS_PER_BIOME,
        "passed": passed,
        "reason": reason,
        "elevation_order": list(graph.elevation_order),
        "biomes": biomes,
    }
    return CheckResult(
        passed,
        reason,
        {
            "found": found,
            "missing": missing,
            "uncovered": uncovered,
            "score": score,
            "max_score": max_score,
            "scorecard": scorecard,
        },
    )


def _lost_summary(lost: list[dict]) -> str:
    parts = []
    for row in lost:
        kind, why = row["kind"], row["why"]
        if kind == "must_connect":
            parts.append(f"not connected to {row['expected']}")
        elif kind == "must_connect_any":
            parts.append(f"not connected to any of {row['expected']}")
        elif kind == "must_not_connect":
            parts.append(f"incorrectly connected to {row['expected']}")
        elif kind == "higher_than":
            other = row["id"].split(".", 1)[1]
            if why == "missing_elevation":
                parts.append(f"missing elevation data for {other}")
            else:
                parts.append(f"not at a higher elevation than {other}")
        else:
            parts.append(why)
    return "; ".join(parts)


def _uncovered(bid: str) -> dict:
    return {
        "score": 0,
        "max_score": POINTS_PER_BIOME,
        "passed": False,
        "covered": False,
        "neighbors": [],
        "elevation_rank": None,
        "evidence": "not in source",
        "summary": "not covered",
        "earned": [],
        "lost": [{"id": "coverage", "kind": "coverage", "why": "not_covered"}],
        "skipped": [],
    }


def _grade_one(bid: str, rules: dict, adj: dict, rank: dict, evidence: str, covered: dict[str, bool]) -> dict:
    neighbors = sorted(adj.get(bid, set()))
    earned, lost = [], []
    # Rules about a biome that is not covered are skipped, not failed: that
    # biome already lost its own 2 points, and failing every neighbor's rule
    # too would charge one absence 4-5 times.
    skipped = sorted({
        other
        for key in ("must_connect", "must_not_connect", "higher_than", "must_connect_any")
        for other in rules.get(key, [])
        if not covered.get(other)
    })
    rules = {
        key: [o for o in vals if covered.get(o)] if isinstance(vals, list) else vals
        for key, vals in rules.items()
    }
    if "must_connect_any" in rules and not rules["must_connect_any"]:
        del rules["must_connect_any"]

    for req in rules.get("must_connect", []):
        row = {
            "id": f"must_connect.{req}",
            "kind": "must_connect",
            "expected": req,
            "actual_neighbors": neighbors,
        }
        if req in adj.get(bid, set()):
            earned.append(row)
        else:
            row["why"] = "not_connected"
            lost.append(row)

    if "must_connect_any" in rules:
        opts = rules["must_connect_any"]
        row = {
            "id": "must_connect_any",
            "kind": "must_connect_any",
            "expected": opts,
            "actual_neighbors": neighbors,
        }
        if any(o in adj.get(bid, set()) for o in opts):
            earned.append(row)
        else:
            row["why"] = "not_connected_to_any"
            lost.append(row)

    for bad in rules.get("must_not_connect", []):
        row = {
            "id": f"must_not_connect.{bad}",
            "kind": "must_not_connect",
            "expected": bad,
            "actual_neighbors": neighbors,
        }
        if bad in adj.get(bid, set()):
            row["why"] = "incorrectly_connected"
            lost.append(row)
        else:
            earned.append(row)

    for hi in rules.get("higher_than", []):
        row = {
            "id": f"higher_than.{hi}",
            "kind": "higher_than",
            "expected": f"{bid} before {hi} in elevation_order",
            "actual": {f"{bid}_rank": rank.get(bid), f"{hi}_rank": rank.get(hi)},
        }
        if bid not in rank or hi not in rank:
            row["why"] = "missing_elevation"
            lost.append(row)
        elif rank[bid] >= rank[hi]:
            row["why"] = "not_higher"
            lost.append(row)
        else:
            earned.append(row)

    ok = not lost
    return {
        "score": COVERAGE_POINTS + (PLACEMENT_POINTS if ok else 0),
        "max_score": POINTS_PER_BIOME,
        "passed": ok,
        "covered": True,
        "skipped": skipped,
        "neighbors": neighbors,
        "elevation_rank": rank.get(bid),
        "evidence": evidence,
        "summary": "ok" if ok else _lost_summary(lost),
        "earned": earned,
        "lost": lost,
    }
