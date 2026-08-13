from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from llm import CheckResult, ExtractedGraph

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


def grade_graph(graph: ExtractedGraph) -> CheckResult:
    adj: dict[str, set[str]] = defaultdict(set)
    for node in graph.nodes:
        for n in node.neighbors:
            adj[node.id].add(n)
            adj[n].add(node.id)
    rank = {b: i for i, b in enumerate(graph.elevation_order)}

    found, missing = {}, {}
    for bid, rules in RULES.items():
        ok, why = _grade_one(bid, rules, adj, rank)
        (found if ok else missing)[bid] = why

    score, max_score = len(found), len(RULES)
    passed = not missing
    reason = "All biomes correctly placed" if passed else f"Missing {len(missing)}/{max_score} biomes: {', '.join(missing)}"
    return CheckResult(passed, reason, {"found": found, "missing": missing, "score": score, "max_score": max_score})


def _grade_one(bid, rules, adj, rank):
    for req in rules.get("must_connect", []):
        if req not in adj.get(bid, set()):
            return False, f"not connected to {req}"
    if "must_connect_any" in rules:
        opts = rules["must_connect_any"]
        if not any(o in adj.get(bid, set()) for o in opts):
            return False, f"not connected to any of {opts}"
    for bad in rules.get("must_not_connect", []):
        if bad in adj.get(bid, set()):
            return False, f"incorrectly connected to {bad}"
    for hi in rules.get("higher_than", []):
        if bid not in rank or hi not in rank:
            return False, f"missing elevation data for {bid} or {hi}"
        if rank[bid] >= rank[hi]:
            return False, f"not at a higher elevation than {hi}"
    return True, "ok"
