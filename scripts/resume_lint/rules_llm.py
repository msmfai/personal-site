"""LLM-judged rules. One structured call over the whole resume, findings keyed to unit ids.

Judge rules carry facet needs like code rules; only the active ones are sent, and
the judge adopts a persona composed from the active audience, role, and specialisms.
"""
from __future__ import annotations

import os
import re
from typing import Literal

from pydantic import BaseModel, Field

from .model import Finding, Resume
from .facets import is_active, persona

MODEL = os.environ.get("RESUME_LINT_MODEL", "claude-opus-5")

# (rule id, needs, description). needs: a value, a tuple (all of), or a list (any of); () = always.
JUDGE_RULES: list[tuple[str, tuple, str]] = [
    ("L01-impact", (), "Bullet describes an activity, not an outcome. What changed because you did it?"),
    ("L02-specificity", (), "A peer could not tell from the bullet what was actually done."),
    ("L03-readability", (), "The reader would have to re-read this to parse it."),
    ("L04-claim-fit", (), "The claim is stronger or weaker than the evidence in the same bullet supports."),
    ("L05-tone", (), "Reads as apologetic, inflated, or performing modesty."),
    ("L06-redundant", (), "Says something another unit already says (name the other unit id)."),
    ("L07-so-what", (), "True and specific, but the reader can't see why it matters for the role."),
    ("L09-throughline", (), "(summary only) Lists areas rather than stating the thread that connects them."),
    ("L10-consistency", (), "Summary or label claims something the body doesn't evidence, or omits something the body shows."),
    ("L11-ordering", (), "The strongest bullet in an entry is not first."),
    ("L12-jargon", (), "Term this reader may not know, left unexplained."),
    ("L14-skills", (), "Skill keyword that reads as padding or is not defensible at interview depth given the body."),
    ("L15-slop", (), "Reads as AI-generated: stock verbs, symmetrical phrasing, generic claims with no niche obstacle or specific tool. Watch especially for Claude's habits: 'not X but Y' reframes, colon set-ups, punchy 'so X stops being Y' closers, rhetorical framing ('a question every…'), reflexive triads, and words like genuinely, actually, crucially, nuanced, landscape."),
    ("L16-voice", (), "Doesn't sound like a specific person; could be pasted into anyone's resume."),
    ("L-OW01-origination", (["ai-scientist", "research-engineer"],), "Research item where the reader can't tell the idea was the candidate's own. Range reads as versatility only when each piece is visibly originated."),
    ("L-OW02-thread", (["ai-scientist", "research-engineer"],), "(summary) The through-line connecting the fields is absent or stated as a list of areas rather than a method or question."),
    ("L13-publication", (["ai-scientist", "research-engineer", "academia"],), "Publication line has an issue: author formatting, venue naming, or something a reader would trip on."),
    ("L08-lone-wolf", (["big-tech", "frontier-lab", "trading-firm"],), "Wording implies working alone or not collaborating, where that isn't the intent."),
    # role
    ("L-SC01-contribution", ("ai-scientist",), "The scientific contribution (what was found, and why it matters) isn't stated in one clause a peer could repeat."),
    ("L-SC02-independence", ("ai-scientist",), "Can't tell whether this person drove the research or assisted it."),
    ("L-RE01-bridge", ("research-engineer",), "Research and engineering are listed side by side but nothing shows one turning into the other."),
    ("L-RE02-tooling", ("research-engineer",), "Infrastructure or tooling is implied but not owned: what did you build that others ran on?"),
    ("L-EN01-scope", ("engineer",), "Scope of ownership is unclear: component, service, or system; solo or team; how many users."),
    ("L-EN02-design", ("engineer",), "No evidence of system design decisions and their trade-offs."),
    # specialism
    ("L-GR01-fluency", ("graphics",), "Rendering work described in ML terms; a graphics reader wants pipeline, budget, and visual result."),
    ("L-GR02-ml-gloss", ("graphics",), "ML method named without saying what it did for the image or the frame."),
    ("L-MS01-translate", ("materials-science",), "Materials work stated in chemistry terms that a non-chemist reader can't weight."),
    ("L-EV01-rigor", ("ml-evaluation",), "Evaluation claim without the control, baseline, or confound handling an evaluator expects."),
    ("L-HPC01-scale", ("hpc-systems",), "Distributed or GPU work without the scale, speedup, or utilisation number that proves it."),
    # audience
    ("L-AI01-scale", ("frontier-lab",), "Nothing tells a lab lead whether this person has trained or evaluated models at scale, with real compute."),
    ("L-AI02-translate", ("frontier-lab",), "Games-industry achievement stated in games terms; an ML reader can't tell what it's worth."),
    ("L-AI03-rigor", ("frontier-lab",), "A claim an ML reviewer would want a control or baseline for, stated without one."),
    ("L-CO01-value", ("buyer",), "A buyer can't see what a client got: outcome, artefact, decision, or saved cost."),
    ("L-CO02-accessible", ("buyer",), "Written for an academic reviewer, not a buyer; the buyer will bounce."),
    ("L-CO03-credibility", ("buyer",), "The credential that would make a buyer trust this person is present but buried."),
    ("L-QU01-rigor", ("trading-firm",), "Quantitative claim without the method or the number a quant reader expects."),
    ("L-QU02-register", ("trading-firm",), "Register is warmer or wordier than the terse, impersonal style quant firms read fastest."),
    ("L-FO01-agency", ("investor",), "Reads as a contributor or employee where the investor wants to see ownership and shipping."),
    ("L-FO02-story", ("investor",), "The document doesn't add up to a one-sentence story of what this person builds and why."),
]


def _system(active: set[str], who: str | None = None, extra: list | None = None) -> str:
    rules = "\n".join(f"{rid:20} {desc}" for rid, needs, desc in JUDGE_RULES + (extra or []) if is_active(needs, active))
    return f"""You are {who or persona(active)}, reviewing a resume with exacting standards.
You will receive the resume as a list of units, each with an id, kind, and text. Produce individual findings, one per issue, each anchored to exactly one unit id.

Rules you may report (use the id verbatim; report nothing outside this list):
{rules}

Standards:
- Report only real problems this reader would notice. Skip praise. Skip anything trivial.
- Each finding: the rule id, the unit id, severity (error for something that damages the candidate with this reader, warn for something they would mark, info for a judgement call), a one-sentence diagnosis, and a concrete rewrite or fix.
- Rewrites must keep every fact; do not invent numbers, outcomes, or claims. If a fix needs a fact the resume doesn't contain, say so in the suggestion.
- Prefer fewer, sharper findings over many weak ones.
- Breadth across fields is NOT a defect and must not be reported as one. Do not recommend narrowing, dropping a field, or picking a lane. A versatile researcher who originates work in several fields is a strength; the only failure modes are (a) the reader can't see the work was originated by the candidate, and (b) the summary doesn't name what connects it. Report those, never the breadth itself.
- Do not push toward stock "power verbs" (spearheaded, leveraged, orchestrated); those are now read as AI slop. Plain, specific verbs win.
- Then give a whole-document read from this reader's chair: the top issues in priority order, and one sentence each for the most and least flattering honest impression the document leaves on them."""


class LLMFinding(BaseModel):
    rule: str = Field(description="Rule id, e.g. L01-impact")
    unit_id: str = Field(description="The id of the unit the finding is anchored to")
    severity: Literal["error", "warn", "info"]
    message: str
    suggestion: str


class LLMReport(BaseModel):
    findings: list[LLMFinding]
    top_issues: list[str] = Field(description="Whole-document issues, most important first, at most five")
    most_flattering_read: str
    least_flattering_read: str


def _render_units(r: Resume) -> str:
    lines = []
    for u in r.units:
        ctx = f" [{u.meta.get('company')}]" if u.meta.get("company") else ""
        lines.append(f"{u.id} ({u.kind}{ctx}): {u.text}")
    return "\n".join(lines)


def run(r: Resume, active: set[str], effort: str = "high", who: str | None = None, extra: list | None = None,
        tag: str = "") -> tuple[list[Finding], LLMReport | None, str]:
    """Returns (findings, report, note). `note` explains a skipped run or reports usage."""
    try:
        import anthropic
    except ImportError:
        return [], None, "anthropic SDK not installed; LLM rules skipped"
    client = anthropic.Anthropic()
    try:
        with client.messages.stream(
            model=MODEL,
            max_tokens=16000,
            system=_system(active, who, extra),
            output_config={"effort": effort},
            output_format=LLMReport,
            messages=[{"role": "user", "content": "Resume units:\n\n" + _render_units(r)}],
        ) as stream:
            response = stream.get_final_message()
    except (anthropic.AuthenticationError, TypeError):
        # The SDK raises TypeError at request time when no credential source resolves.
        return [], None, "no API credentials (set ANTHROPIC_API_KEY or run `ant auth login`); LLM rules skipped"
    except anthropic.APIConnectionError as e:
        return [], None, f"could not reach the API ({e}); LLM rules skipped"
    if response.stop_reason == "refusal":
        return [], None, "model declined the request; LLM rules skipped"
    report: LLMReport = response.parsed_output
    source_numbers = set(re.findall(r"\d+(?:\.\d+)?", r.raw))
    by_id = {u.id: u for u in r.units}
    out = []
    for f in report.findings:
        u = by_id.get(f.unit_id)
        out.append(Finding(f"{tag}{f.rule}", f.severity, u.line if u else 0, u.path if u else f.unit_id, f.message, f.suggestion, source="llm"))
        invented = sorted(set(re.findall(r"\d+(?:\.\d+)?", f.suggestion)) - source_numbers)
        if invented:
            out.append(Finding("G01-ungrounded", "error", u.line if u else 0, u.path if u else f.unit_id,
                               f"Judge's rewrite for {f.rule} introduces number(s) not in the source: {', '.join(invented)}",
                               "Do not apply that rewrite as written. Use only numbers you can evidence.", source="llm"))
    usage = response.usage
    return out, report, f"LLM: {MODEL} as {persona(active)}; {usage.input_tokens} in / {usage.output_tokens} out"
