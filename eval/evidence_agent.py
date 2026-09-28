"""An agentic code-evidence hunter for the judges.

A one-shot probe reads the whole source once and answers every item from
that single pass. That misses features the code builds *implicitly*: a
desert whose height function is `Math.round(32*t/5)*5` over a noise
threshold builds stepped sandstone mesas, and its colour function paints
anything above a height band a darker ochre, but no identifier says
"sandstone", "mesa" or "peak". A single pass cited that very line as the
*flat* basin and reported the peaks absent, while the rendered frames
plainly showed them.

This agent gets the same question for one item and can investigate: grep
for the biome and for synonyms, read the branches it finds, follow helper
calls, and reason about what the math produces — through the read-only
tools in harness/code_tools.py (a temp copy of the file; nothing here can
write, and the real file is hash-checked before and after).

Its answer is not trusted either: every quoted line must really be in the
source (eval/evidence.py), exactly like the one-shot probes'. The agent can
only *find* evidence faster; it can't make any up.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from langchain.agents import create_agent
from langchain.agents.middleware import wrap_model_call
from langchain_core.messages import HumanMessage
from langsmith import traceable
from pydantic import BaseModel, Field

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.append(str(_ROOT))

from eval.capture.llm import call_with_retry, chat  # noqa: E402
from eval.evidence import in_source, normalize, strip_to_js  # noqa: E402
from harness.code_tools import ReadOnlySource  # noqa: E402
from harness.status import log  # noqa: E402

# The agent is a judge, not the model under test, so its spend is bounded:
# one LangGraph step is one model call or one tool call. 40 is ~15-20 tool
# calls, enough to search, read, follow a helper, and confirm.
RECURSION_LIMIT = 40


class EvidenceVerdict(BaseModel):
    found: bool = Field(description="True only if SOURCE code builds this feature in this biome.")
    evidence: str = Field(
        default="",
        description="Verbatim source lines that build it, copied WITHOUT the `N: ` prefix, newline-separated. "
        "Empty when found is false.",
    )
    lines: list[int] = Field(default_factory=list, description="Line numbers of the evidence lines.")
    explanation: str = Field(description="One or two sentences: how this code produces the feature, or what you searched.")


SYSTEM_PROMPT = """You verify whether a generated Three.js world (world.html) really builds one feature in one biome.
You have read-only tools over the file: grep (regex, returns `N: line`), read_lines(start, end), and shell (read-only
grep/sed -n/head/tail/wc/nl/cut/sort/uniq pipelines on world.html).

How to hunt:
1. Find the biome's code. grep its name and aliases (ids, enum constants, abbreviations). Look for its terrain/height
   function, its colour/material branch, its flora/fauna placement, and its weather emitters.
2. Read those regions. Features are often built WITHOUT a descriptive name: work out what the math produces.
3. Follow helpers: if a branch calls placeX(...) or pushes into a table, find the function or loop that consumes it.
4. Decide. found is true only if code places/raises/colours/emits the feature inside this biome. A comment, a legend
   entry, an enum, a config row nothing consumes, or a keyword in another biome's branch is NOT evidence.
   The code must build THIS feature, not just the biome around it: "there are pools, so there must be banks" or
   "the ground is dark, so it must be mud" is inference, not evidence. Every quoted line must do part of the work,
   and the explanation must say which property of the feature each line produces. If no line builds the feature's
   defining property, found is false — even if the frames seem to show it.
5. Quote. Copy the lines that build it exactly as the tools printed them, minus the `N: ` prefix. Several lines are
   fine; the same line may be evidence for several features.

Examples (the code is illustrative; every world names things differently):

Example 1 — built implicitly by math. Feature: "rock peaks rising from a flat basin".
  shell: grep -n -i -E "basin|B\\.ARID|arid" world.html | head -20
  -> 212: {id:B.ARID,cx:40,cz:70,rx:38,rz:30,base:9,feat:(x,z)=>{
  read_lines(212, 218)
  -> 214:   const k=smoothstep(0.6,0.72,noise(x*0.03,z*0.03));
  -> 215:   return Math.floor(28*k/4)*4 + 2*fbm(x*0.1,z*0.1);
  grep: "case B\\.ARID" -> 460:   case B.ARID: return h>SEA+12 ? 0xb07a45 : 0xe0c27a;
  Reasoning: k is 0 over most of the basin (flat) and rises to 1 in noise patches, so line 215 raises stepped blocks up
  to 28 high there; line 460 colours anything above the height band a darker rock tone. found=true, evidence = lines 214,
  215 and 460.

Example 2 — a named helper placed in the biome's own cells. Feature: "cacti across the flats".
  grep: "cact" -> 301: function cactus(x,h,z){ ... }   and   344:   if(bio===B.ARID && r<0.05) cactus(x,h,z);
  found=true, evidence = line 344 (the placement inside this biome), not only the helper definition.

Example 3 — a table only counts if something consumes it. Feature: "foxes in the desert".
  grep: "fox" -> 902: const FAUNA=[{t:'fox',x:40,z:70,n:6}, ...];
  grep: "FAUNA" -> 1010: for(const f of FAUNA){ for(let i=0;i<f.n;i++) spawn(f.t, f.x+..., f.z+...); }
  found=true, evidence = lines 902 and 1010. With no consumer, found=false.

Example 4 — genuinely absent. Feature: "dead bushes".
  grep -i: "bush|shrub|twig|dead|scrub" -> matches only in another biome's branch, or none.
  Read the biome's flora placement: it places only cacti and rocks.
  found=false, evidence="", explanation says what you searched and read.

The rendered frames may be quoted to you as a hint. They can be wrong (a camera can frame the wrong region): confirm
in code, never from the hint alone. Finish with the structured answer."""


@wrap_model_call
def _judge_rate_limit(request, handler):
    """Every model call this agent makes goes through the judge's shared
    throttle and 429 backoff (eval/capture/llm.py), like any single judge call."""
    return call_with_retry(lambda: handler(request))


def _logged(tools: list, label: str) -> list:
    """Print every tool call and a one-line result, like every other judge step."""
    for t in tools:
        original = t.func

        def run(*args, _original=original, _name=t.name, **kwargs):
            out = _original(*args, **kwargs)
            first = out.splitlines()[0] if out else ""
            log(f"      {label}  {_name}({', '.join(f'{k}={v!r}' for k, v in kwargs.items())}) -> {first[:100]}")
            return out

        t.func = run
    return tools


@traceable(name="evidence_agent::hunt", run_type="chain")
def hunt(
    html_path: str | Path,
    *,
    biome: str,
    aliases: list[str],
    feature: str,
    visual_hint: str | None = None,
    model: str | None = None,
) -> tuple[EvidenceVerdict, bool]:
    """Investigate one feature in one biome. Returns (verdict, verified):
    `verified` is True only when found=true and the quoted evidence is really
    in the source. The file at html_path is never exposed to the agent, and is
    checked unchanged afterwards."""
    html_path = Path(html_path)
    before = hashlib.sha256(html_path.read_bytes()).hexdigest()
    label = f"hunt {biome}/{feature[:40]}"
    task = (
        f"Biome: {biome} (source aliases: {', '.join(aliases) or 'unknown'})\n"
        f"Feature: {feature}\n"
        + (f"Hint — the rendered frames appear to show: {visual_hint}\n" if visual_hint else "")
        + "Does world.html build this feature in this biome?"
    )
    with ReadOnlySource(html_path.read_text(encoding="utf-8", errors="ignore")) as source:
        agent = create_agent(
            model=chat(model, temperature=0.0),
            tools=_logged(source.tools(), label),
            system_prompt=SYSTEM_PROMPT,
            middleware=[_judge_rate_limit],
            response_format=EvidenceVerdict,
        )
        log(f"      {label}  start")
        result = agent.invoke({"messages": [HumanMessage(content=task)]}, config={"recursion_limit": RECURSION_LIMIT})
    if hashlib.sha256(html_path.read_bytes()).hexdigest() != before:
        raise RuntimeError(f"{html_path} changed during an evidence hunt — the read-only boundary failed")

    verdict = result.get("structured_response")
    if not isinstance(verdict, EvidenceVerdict):
        verdict = EvidenceVerdict(found=False, explanation="agent returned no structured answer")
    verified = bool(
        verdict.found and verdict.evidence.strip() and in_source(verdict.evidence, normalize(strip_to_js(html_path)))
    )
    log(
        f"      {label}  -> found={verdict.found} verified={verified}"
        + (f" lines={verdict.lines}" if verdict.lines else "")
    )
    return verdict, verified
