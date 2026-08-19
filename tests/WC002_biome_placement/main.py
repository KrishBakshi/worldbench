"""strip → classify → extract → grade.

Writes classified.json, graph.json (website), graph.svg (local preview),
and score.json (per-rule earned/lost, including elevation ranks).

    uv run python tests/WC002_biome_placement/main.py [world.html] [out_dir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from classify import classify_biome_js
from extract import extract_graph
from grade import grade_graph
from plot import write_graph
from llm import CheckResult, ClassifiedBiomeJS, ExtractedGraph

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.append(str(_ROOT))
from harness.status import log  # noqa: E402

def write_artifacts(html_path: str, out_dir: Path, classified: ClassifiedBiomeJS, graph: ExtractedGraph, result: CheckResult) -> dict:
    classified_path = out_dir / "classified.json"
    classified_path.write_text(classified.model_dump_json(indent=2), encoding="utf-8")
    files = write_graph(graph, result, out_dir / "graph.json", out_dir / "graph.svg")
    score_path = out_dir / "score.json"
    score_path.write_text(json.dumps(result.details["scorecard"], indent=2) + "\n", encoding="utf-8")
    return {"classified": classified_path.name, "score": score_path.name, **files}


def check_biome_placement(html_path: str, out_dir: Path, model: str | None = None) -> CheckResult:
    log("      classify  (llm)")
    classified = classify_biome_js(html_path, model)
    log("      extract   (llm)")
    graph = extract_graph(classified, model)
    log("      grade")
    result = grade_graph(graph)
    result.details["artifacts"] = write_artifacts(html_path, out_dir, classified, graph, result)
    return result


if __name__ == "__main__":
    path = sys.argv[1]
    out_dir = Path(sys.argv[2]) / f"{Path(path).parent.name}__WC002_biome_placement"
    out_dir.mkdir(parents=True, exist_ok=True)
    log(f"WC002  {path}")
    result = check_biome_placement(path, out_dir)
    print(f"passed={result.passed} score={result.details['score']}/{result.details['max_score']}", flush=True)
    print(result.reason, flush=True)
    for name in ("classified.json", "graph.json", "graph.svg", "score.json"):
        print(f"{out_dir}/{name}", flush=True)
