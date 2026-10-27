"""Consensus hard lints the survey turned up: AI-slop tells, metric context, page budget, ownership framing.

Slop tells are what recruiters now screen for (em dashes, AI-favourite verbs, symmetrical bullets,
context-free metrics, placeholder residue). Ownership framing is the counter to the "scattered
portfolio" heuristic: breadth is neutral; what must be present is evidence that each piece was
originated by the candidate and that the summary names the thread.
"""
from __future__ import annotations

import re
import statistics

from .facets import rule
from .model import Finding, Resume, strip_markdown, words

AI_VERBS = r"\b(spearhead\w*|leverag\w*|orchestrat\w*|delv\w*|pivotal|intricate|meticulous\w*|showcas\w*|harness\w*|elevat\w*|empower\w*|foster\w*|streamlin\w*|tapestry|underscor\w*|bolster\w*|honed|multifaceted|synerg\w*|championed|spearheaded)\b"
PLACEHOLDER = r"(\[[A-Z][A-Za-z ]+\](?!\()|\bTODO\b|\bTBD\b|lorem ipsum|\bXX%|\bN%|\{\{|\}\})"
CONTEXT_WORDS = r"\b(from|to|vs\.?|versus|baseline|relative|compared|over|across|per|out of|of the)\b"
OWNERSHIP = r"\b(conceived|proposed|initiated|originated|designed|led|independently|sole|end[- ]to[- ]end|my own|first[- ]author|devised|invented|formulated|identified)\b"

LINES_PER_PAGE = 54       # non-blank lines per page; the survey's 52-56 rule of thumb
CHARS_PER_LINE = 120      # calibrated 2026-09-26: estimate 115 vs 91 real lines at 105


def _f(rule_id, sev, u, msg, sug=""):
    return Finding(rule_id, sev, u.line, u.path, msg, sug)


@rule("universal")
def rule_em_dash(r: Resume):
    out = []
    for u in r.units:
        n = u.text.count("—") + u.text.count(" – ")
        if n:
            out.append(_f("T23-em-dash", "warn", u, f"{n} em/en dash(es) in running text; the most-cited AI-writing tell in 2026 screening",
                          "Use a comma, a full stop, or parentheses. Keep en dashes only in date and number ranges."))
    return out


@rule("universal")
def rule_ai_verbs(r: Resume):
    out = []
    rx = re.compile(AI_VERBS, re.I)
    for u in r.units_of("summary", "entry_summary", "highlight", "pub_summary", "label"):
        hits = sorted({m.group(0).lower() for m in rx.finditer(strip_markdown(u.text))})
        if hits:
            out.append(_f("T24-ai-verb", "warn", u, f"AI-favourite word(s) recruiters flag: {', '.join(hits)}",
                          "Use the plain verb for what you did: built, measured, cut, proved, ran."))
    return out


@rule("universal")
def rule_bullet_symmetry(r: Resume):
    out = []
    by_entry: dict[str, list] = {}
    for u in r.units_of("highlight"):
        by_entry.setdefault(u.entry, []).append(u)
    for entry, us in by_entry.items():
        if len(us) < 3:
            continue
        lens = [len(words(u.text)) for u in us]
        if statistics.pstdev(lens) < 2.0:
            out.append(_f("T25-symmetry", "info", us[0], f"All {len(us)} bullets are within a couple of words of each other ({min(lens)}-{max(lens)} words)",
                          "Uniform bullet length reads as generated. Let the important bullet be long and the minor one short."))
    return out


@rule("universal")
def rule_metric_context(r: Resume):
    out = []
    for u in r.units_of("highlight"):
        text = strip_markdown(u.text)
        if re.search(r"\d+(\.\d+)?\s*(%|x\b|×)", text) and not re.search(CONTEXT_WORDS, text, re.I):
            out.append(_f("T26-metric-context", "info", u, "Percentage or multiplier with no baseline or comparison in the same bullet",
                          "Say what it was relative to: 'from 10 GB to 5 GB', 'vs the deployed baseline'. Context-free metrics read as inflated."))
    return out


@rule("universal")
def rule_placeholder(r: Resume):
    return [_f("T27-placeholder", "error", u, "Placeholder or template residue left in the text")
            for u in r.units if re.search(PLACEHOLDER, u.text)]


@rule("universal")
def rule_line_budget(r: Resume):
    """Estimate rendered non-blank lines from the source; flag when over the two-page budget and name cut candidates."""
    budget = 2 * LINES_PER_PAGE
    pdf = r.pdf
    if pdf.exists() and pdf.stat().st_mtime >= r.file.stat().st_mtime:
        return []  # a fresh render exists; the PDF page-count rule (S14) is the ground truth
    est = 0
    per_unit = []
    for u in r.units:
        if u.kind in ("keyword", "interest"):
            continue
        n = max(1, -(-len(strip_markdown(u.text)) // CHARS_PER_LINE))
        est += n
        if u.kind == "highlight":
            per_unit.append((n, u))
    # headings, entry heading lines, skills/interests groups: rough fixed overhead
    est += 2 * len(r.entries("Experience")) + 2 * len(r.entries("Education")) + 2 * (len(r.entries("Skills")) + len(r.entries("Interests"))) + 8
    if est > budget:
        longest = sorted(per_unit, key=lambda t: -t[0])[:3]
        cands = "; ".join(f"{u.path} ({n} lines)" for n, u in longest)
        first = next(iter(r.units), None)
        return [Finding("S18-line-budget", "warn", first.line if first else 0, "document",
                        f"Estimated {est} rendered lines against a budget of {budget} (two pages)",
                        f"Cut order: trim the longest bullets first: {cands}. Then Interests, then Skills groups.")]
    return []


@rule(["ai-scientist", "research-engineer"])
def rule_ownership_signal(r: Resume):
    """Breadth is not a defect. Each research item should show it was originated, so range reads as versatility."""
    out = []
    rx = re.compile(OWNERSHIP, re.I)
    surname = (r.cv.get("name") or "").split(" ")[-1].lower()
    for u in r.units_of("highlight"):
        if re.search(r"\b(paper|published|accepted|neurips|siggraph|transactions|journal|preprint|arxiv)\b", u.text, re.I) and not rx.search(u.text):
            out.append(_f("R-OW01-ownership", "warn", u, "Research bullet names a paper but not your role in originating it",
                          "If the idea was yours, say so in one word: 'Conceived and led…', 'Proposed…', 'Independently…'. Range without ownership reads as scatter; range with ownership reads as versatility."))
    for u in r.units_of("summary"):
        if not re.search(r"\b(thread|connect|common|across|same|both|from .* to|bring|apply|carry)\b", u.text, re.I):
            out.append(_f("R-OW02-thread", "warn", u, "Summary does not state what connects the fields you've worked in",
                          "One sentence naming the through-line turns three fields into one method. Without it a reader supplies 'unfocused'."))
    return out


RULES = [v for k, v in sorted(globals().items()) if k.startswith("rule_")]
