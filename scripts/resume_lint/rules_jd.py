"""Job-description facet: the one thing every surveyed pipeline does. Active only when a JD is supplied.

Scores are uncalibrated by design ("models the screen, isn't the screen"); findings say what's
missing and where it could credibly go, and never suggest adding a skill the body can't support.
"""
from __future__ import annotations

import re
from pathlib import Path

from .model import Finding, Resume, strip_markdown

STOP = set("""a an the and or of to in for with on at by from as is are be this that we you our your will can may should
must have has had it its their they them who what which how about into over under across than then also such via using
use used etc experience experienced strong ability team work working role roles years year plus preferred required
requirements responsibilities qualifications degree including include skills skill knowledge""".split())

ALIASES = {"llm": "large language models", "llms": "large language models", "ml": "machine learning", "rl": "reinforcement learning",
           "nlp": "natural language processing", "cv": "computer vision", "gnn": "graph neural networks", "hpc": "high performance computing"}


def _terms(text: str) -> set[str]:
    text = strip_markdown(text).lower()
    toks = re.findall(r"[a-z][a-z0-9\+\#\.\-]{1,}", text)
    out = set()
    for t in toks:
        t = t.strip(".-")
        if len(t) < 3 and t not in ("c#", "go", "r"):
            continue
        if t in STOP:
            continue
        out.add(ALIASES.get(t, t))
    for m in re.finditer(r"\b([a-z]+ [a-z]+)\b", text):  # bigrams
        a, b = m.group(1).split()
        if a not in STOP and b not in STOP:
            out.add(m.group(1))
    return out


def run(r: Resume, jd_path: Path) -> list[Finding]:
    jd = jd_path.read_text(encoding="utf-8")
    if jd.startswith("---"):  # role.md from the brand studio: drop YAML frontmatter, title from first heading
        jd = jd.split("---", 2)[-1]
        jd = re.sub(r"^\s*#\s*", "", jd.lstrip(), count=1)
        m = re.search(r"^## The posting.*?$(.*?)(?=^## |\Z)", jd, re.M | re.S)  # only the posting, not our notes
        if m:
            jd = jd.lstrip().splitlines()[0] + "\n" + m.group(1)
    jd_terms = _terms(jd)
    body = " ".join(u.text for u in r.units_of("highlight", "entry_summary", "summary", "pub_title"))
    body_terms = _terms(body)
    skill_terms = _terms(" ".join(u.text for u in r.units_of("keyword")))
    out = []

    # Title match: does the JD's first line / title phrase appear anywhere?
    title = jd.strip().splitlines()[0].strip().lower() if jd.strip() else ""
    label = (r.cv.get("label") or "").lower() + " " + (r.cv.get("summary") or "").lower()
    if title and len(title) < 80 and not any(w in label for w in re.findall(r"[a-z]+", title) if len(w) > 4):
        first = next(iter(r.units_of("label")), None)
        out.append(Finding("J01-title", "info", first.line if first else 0, "cv.label", f"JD title '{title}' shares no distinctive word with your label or summary",
                           "If the role name is one you'd accept, echo it once; screeners search for it."))

    # Coverage: JD terms present in body (weighted), present only in skills, or absent.
    in_body = jd_terms & body_terms
    only_skills = (jd_terms & skill_terms) - body_terms
    missing = jd_terms - body_terms - skill_terms
    # Keep only multiword or technical-looking terms for the missing list, to avoid noise.
    missing = sorted(t for t in missing if " " in t or re.search(r"[\+\#\d\-]|^[a-z]{5,}$", t))[:25]
    first = next(iter(r.units_of("summary")), None)
    ln = first.line if first else 0
    cov = len(in_body) + 0.5 * len(only_skills)
    total = max(1, len(jd_terms))
    out.append(Finding("J02-coverage", "info", ln, "document",
                       f"JD term coverage {cov / total:.0%} (uncalibrated): {len(in_body)} in bullets, {len(only_skills)} only in Skills, {len(missing)} absent",
                       "Terms shown in bullets count double with every scorer surveyed; a term only in Skills is half credit."))
    if only_skills:
        out.append(Finding("J03-skills-only", "info", ln, "Skills", f"JD terms you list but never demonstrate: {', '.join(sorted(only_skills)[:15])}",
                           "Move each into the bullet where it was actually used, or accept half credit."))
    if missing:
        out.append(Finding("J04-missing", "info", ln, "document", f"JD terms absent from the resume: {', '.join(missing)}",
                           "Add only the ones the body can truthfully support; anything else is fabrication, and screeners now check context."))
    return out
