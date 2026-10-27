"""Deterministic structural rules over the whole resume (dates, sections, duplicates, PDF)."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from .facets import rule
from .model import Finding, Resume, Unit, strip_markdown, words

DATE_RE = re.compile(r"^\d{4}(-(0[1-9]|1[0-2]))?$")  # a version may date an entry to the year only
EXPECTED_ORDER = ["Experience", "Education", "Publications", "Skills", "Interests"]


def _entry_line(r: Resume, section: str, idx: int) -> int:
    us = [u for u in r.units if u.entry == f"{ {'Experience': 'exp', 'Education': 'edu', 'Publications': 'pub'}.get(section, section.lower())}[{idx}]"]
    return min((u.line for u in us), default=0)


def _f(rule, sev, line, path, msg, sug=""):
    return Finding(rule, sev, line, path, msg, sug)


def _parse(d) -> date | None:
    s = str(d or "").strip()
    if s.lower() == "present":
        return date.today()
    if DATE_RE.match(s):
        y, _, m = s.partition("-")
        return date(int(y), int(m or 1), 1)
    return None


@rule("universal")
def rule_dates(r: Resume):
    out = []
    for section in ("Experience", "Education"):
        for i, e in enumerate(r.entries(section)):
            ln = _entry_line(r, section, i) or 1
            for key in ("start_date", "end_date"):
                v = str(e.get(key, "")).strip()
                if not v:
                    out.append(_f("S01-date", "error", ln, f"{section}[{i}].{key}", f"Missing {key}"))
                elif not DATE_RE.match(v) and v.lower() != "present":
                    out.append(_f("S01-date", "error", ln, f"{section}[{i}].{key}", f"Date '{v}' is not YYYY-MM, YYYY or 'present'"))
            s, en = _parse(e.get("start_date")), _parse(e.get("end_date"))
            if s and en and en < s:
                out.append(_f("S01-date", "error", ln, f"{section}[{i}]", "End date is before start date"))
    return out


@rule("universal")
def rule_reverse_chronological(r: Resume):
    out = []
    for section in ("Experience", "Education"):
        entries = r.entries(section)
        for i in range(1, len(entries)):
            a, b = _parse(entries[i - 1].get("start_date")), _parse(entries[i].get("start_date"))
            ae, be = _parse(entries[i - 1].get("end_date")), _parse(entries[i].get("end_date"))
            if a and b and b > a and not (ae and be and ae >= be):  # ordering by end date is also conventional
                out.append(_f("S02-order", "warn", _entry_line(r, section, i), f"{section}[{i}]",
                              "Entry starts later than the one above it; section is not reverse-chronological",
                              "Order by start date, most recent first (or state the ordering rule in a comment)."))
    return out


@rule("universal")
def rule_missing_fields(r: Resume):
    out = []
    req = {"Experience": ("company", "position", "location", "summary", "highlights"),
           "Education": ("institution", "studyType", "area", "highlights"),
           "Publications": ("title", "summary", "publisher")}
    for section, keys in req.items():
        for i, e in enumerate(r.entries(section)):
            for k in keys:
                if not e.get(k):
                    out.append(_f("S04-missing-field", "warn", _entry_line(r, section, i), f"{section}[{i}].{k}", f"Missing '{k}'"))
    return out


@rule("universal")
def rule_highlight_counts(r: Resume):
    out = []
    for section in ("Experience", "Education"):
        for i, e in enumerate(r.entries(section)):
            n = len(e.get("highlights") or [])
            if n > 5:
                out.append(_f("S05-highlights", "warn", _entry_line(r, section, i), f"{section}[{i}]", f"{n} bullets; readers stop at four or five",
                              "Keep the strongest four and fold the rest into them."))
    return out


@rule("technical")
def rule_skills_size(r: Resume):
    out = []
    total = 0
    for gi, g in enumerate(r.entries("Skills")):
        kws = g.get("keywords") or []
        total += len(kws)
        first = next((u for u in r.units if u.entry == f"skill[{gi}]"), None)
        if len(kws) > 12 and first:
            out.append(_f("S06-skills-group", "warn", first.line, f"Skills[{gi}]", f"{len(kws)} keywords in '{g.get('label')}'",
                          "Cut to the ones you'd defend in an interview today."))
    if total > 40:
        first = next((u for u in r.units if u.kind == "keyword"), None)
        out.append(_f("S07-skills-total", "warn", first.line if first else 0, "Skills", f"{total} skill keywords in total",
                      "Long skill lists read as padding; aim for 25 to 30."))
    return out


SKILL_ALIASES = {
    "large language models": ["llm"], "transformer architectures": ["transformer"], "graph neural networks": ["graph", "gnn"],
    "representation learning": ["representation"], "contrastive learning": ["contrastive", "infomax"],
    "distributed training": ["deepspeed", "multi-gpu"], "hpc": ["slurm", "cluster"], "gpu compute": ["cuda"],
    "real-time physics simulation": ["physics"], "game engines": ["frostbite", "unreal", "unity", "engine"],
    "agentic systems": ["agentic"], "real-time game ai": ["real-time"], "materials science": ["materials"],
    "computational chemistry": ["materials", "crystal"], "crystallography": ["crystal"],
    "frontier ai safety": ["alignment", "frontier"], "scientific ai verification": ["verification", "evaluation"],
    "physics simulation": ["physics"], "low-level systems": ["c++", "memory"], "frostbite": ["frostbite"],
}


@rule("technical")
def rule_skills_evidence(r: Resume):
    """Skill keywords with no trace in the experience/education/publications prose, one finding per group."""
    body = strip_markdown(" ".join(u.text for u in r.units_of("highlight", "entry_summary", "summary", "pub_title", "pub_publisher"))).lower()
    out = []
    for gi, g in enumerate(r.entries("Skills")):
        missing = []
        for u in (x for x in r.units if x.entry == f"skill[{gi}]"):
            core = re.sub(r"\s*\(.*?\)", "", strip_markdown(u.text)).strip().lower()
            probes = [core] + [p.strip().lower() for p in re.split(r"[/,]", core) if p.strip()] + SKILL_ALIASES.get(core, [])
            if not any(x and x in body for x in probes):
                missing.append(u.text)
        first = next((u for u in r.units if u.entry == f"skill[{gi}]"), None)
        if missing and first:
            kws = g.get("keywords") or []
            out.append(_f("S16-skill-unevidenced", "info", first.line, f"Skills[{gi}]",
                          f"{len(missing)} of {len(kws)} '{g.get('label')}' keywords never appear in the body: {', '.join(missing)}",
                          "A reader can only weight skills the bullets demonstrate; cut the rest or add the bullet."))
    return out


def _jaccard(a: str, b: str) -> float:
    A, B = set(w.lower() for w in words(a)), set(w.lower() for w in words(b))
    return len(A & B) / len(A | B) if A | B else 0.0


@rule("universal")
def rule_duplicates(r: Resume):
    out = []
    prose = r.units_of("highlight", "entry_summary", "pub_title")
    for i, a in enumerate(prose):
        for b in prose[i + 1:]:
            if a.entry == b.entry and {a.kind, b.kind} == {"entry_summary", "highlight"}:
                continue
            j = _jaccard(strip_markdown(a.text), strip_markdown(b.text))
            if j > 0.6 or (a.kind == "pub_title" and strip_markdown(a.text).lower() in strip_markdown(b.text).lower()) \
                    or (b.kind == "pub_title" and strip_markdown(b.text).lower() in strip_markdown(a.text).lower()):
                out.append(_f("S08-duplicate", "warn", b.line, b.path, f"Overlaps with {a.path} (line {a.line})",
                              "State each fact once; reference it elsewhere only if the section needs it."))
    return out


@rule("universal")
def rule_summary_length(r: Resume):
    out = []
    for u in r.units_of("summary"):
        n = len(words(u.text))
        if n > 120:
            out.append(_f("S09-summary-length", "error", u.line, u.path, f"Summary is {n} words", "Cut to 60 to 80."))
        elif n > 90:
            out.append(_f("S09-summary-length", "warn", u.line, u.path, f"Summary is {n} words", "Aim for 60 to 80."))
    return out


@rule(["big-tech", "frontier-lab", "trading-firm"])
def rule_name_prefix(r: Resume):
    out = []
    for u in r.units_of("name"):
        if re.match(r"^(Dr|Prof|Mr|Ms|Mrs)\.?\s", u.text):
            out.append(_f("S10-name-prefix", "info", u.line, u.path, "Honorific in the name line",
                          "Convention in research and industry is the bare name; the PhD in Education carries the title."))
    return out


@rule(["ai-scientist", "research-engineer", "academia"])
def rule_publications_self_bold(r: Resume):
    out = []
    surname = (r.cv.get("name") or "").split(" ")[-1].lower()
    for u in r.units_of("pub_summary"):
        if surname and surname in u.text.lower() and not re.search(r"\*\*[^*]*" + re.escape(surname) + r"[^*]*\*\*", u.text, re.I):
            out.append(_f("S11-pub-self-bold", "info", u.line, u.path, "Your name is not bolded in this author list",
                          "Bold it so the reader can find you in long author lists."))
        if surname and surname not in u.text.lower():
            out.append(_f("S11-pub-self-missing", "error", u.line, u.path, "Your name is not in this author list"))
    return out


@rule(["ai-scientist", "academia"])
def rule_section_order(r: Resume):
    present = [s for s in (r.cv.get("sections") or {}).keys()]
    expected = [s for s in EXPECTED_ORDER if s in present]
    actual = [s for s in present if s in EXPECTED_ORDER]
    if actual != expected:
        return [_f("S17-section-order", "info", 0, "cv.sections", f"Section order is {actual}", f"Conventional order is {expected}.")]
    return []


@rule("universal")
def rule_pdf(r: Resume):
    out = []
    pdf = r.pdf
    if not pdf.exists():
        return [_f("S14-pdf", "info", 0, str(pdf), "No built PDF found", "Run scripts/build_resume.py (with --variant for a version).")]
    if pdf.stat().st_mtime < r.file.stat().st_mtime:
        out.append(_f("S14-pdf-stale", "warn", 0, str(pdf), "PDF is older than content.yml", "Rebuild it."))
    try:
        from pypdf import PdfReader
        pages = PdfReader(str(pdf)).pages
        if len(pages) != 2:
            out.append(_f("S14-pdf-pages", "warn", 0, str(pdf), f"PDF is {len(pages)} page(s)", "Target is two."))
        text = "\n".join(p.extract_text() or "" for p in pages)
        for line in text.splitlines():
            w = words(line)
            if len(w) == 1 and len(w[0]) < 12 and not line.strip().isupper():
                out.append(_f("S15-pdf-orphan", "info", 0, str(pdf), f"A line in the PDF holds a single word: '{line.strip()}'",
                              "Trim the bullet by a word or two so it doesn't wrap an orphan."))
    except ImportError:
        out.append(_f("S14-pdf", "info", 0, str(pdf), "pypdf not installed; skipped page and orphan checks"))
    return out


RULES = [v for k, v in sorted(globals().items()) if k.startswith("rule_")]
