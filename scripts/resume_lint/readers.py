"""Reader panels: lint a resume against the named people who will actually decide.

A panel file (kept in the brand studio, next to the role) profiles each decision-maker from
company research: who they are, what they screen for, what costs the candidate with them, and
how they'd read the page. Code checks run per reader; the LLM judge reads once per reader, in
that reader's chair. Every reader cites the research it was built from.

Panel schema (YAML):
  route: free text                 # how the resume reaches them (e.g. "recruiter → board, no ATS")
  max_pages: 1                     # optional page target for this route
  redlines:                        # patterns that must never appear (regex, case-insensitive)
    - {pattern: "\\bdanucore\\b", why: "client is described, never named (WK-41)"}
    - {pattern: "2026", near: "neurips|metacognition", why: "..."}   # only when both are in one unit
  readers:
    - id: ceo
      name: Alan Chang
      role: Co-founder and CEO
      source: ../companies/fuse.md
      persona: one paragraph, written as "you are ..."
      top_third: [{any: [term, ...], why: "..."}]   # must appear in label or summary
      wants:     [{any: [term, ...], why: "...", must: true}]   # must appear somewhere in the body
      avoid:     [{pattern: regex, why: "..."}]      # flagged wherever it appears
      jargon:    [term, ...]                        # terms this reader won't know; flagged in the top third
      judge:     ["rule text the LLM judge applies from this reader's chair", ...]
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from .model import Finding, Resume, strip_markdown

TOP = ("label", "summary")
BODY = ("label", "summary", "highlight", "entry_summary", "pub_title", "pub_publisher", "keyword")


def load_panel(path: Path) -> dict:
    panel = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    for rd in panel.get("readers", []) or []:
        for key in ("id", "name", "persona", "source"):
            if not rd.get(key):
                raise ValueError(f"{path}: reader {rd.get('id') or rd.get('name')!r} is missing {key!r}")
    return panel


def _text(r: Resume, kinds) -> str:
    return strip_markdown(" ".join(u.text for u in r.units_of(*kinds))).lower()


def _first(r: Resume, kinds) -> tuple[int, str]:
    u = next(iter(r.units_of(*kinds)), None)
    return (u.line, u.path) if u else (0, "document")


def run(r: Resume, panel: dict, only: set[str] | None = None) -> list[Finding]:
    out: list[Finding] = []

    for rl in panel.get("redlines", []) or []:
        rx = re.compile(rl["pattern"], re.I)
        near = re.compile(rl["near"], re.I) if rl.get("near") else None
        for u in r.units:
            if rx.search(u.text) and (near is None or near.search(u.text)):
                out.append(Finding("P00-redline", "error", u.line, u.path, f"Redline: {rl['why']}",
                                   f"Remove '{rx.search(u.text).group(0)}' from this unit."))

    if panel.get("max_pages") and r.pdf and r.pdf.exists():
        try:
            from pypdf import PdfReader
            n = len(PdfReader(str(r.pdf)).pages)
            if n > panel["max_pages"]:
                out.append(Finding("P01-pages", "warn", 0, str(r.pdf),
                                   f"{n} pages; this route ({panel.get('route', 'panel')}) targets {panel['max_pages']}",
                                   "Trim the lowest-value entry for these readers before sending."))
        except ImportError:
            pass

    top, body = _text(r, TOP), _text(r, BODY)
    for rd in panel.get("readers", []) or []:
        if only and rd["id"] not in only:
            continue
        who = f"{rd['name']} ({rd.get('role', rd['id'])})"
        for t in rd.get("top_third", []) or []:
            if not any(term.lower() in top for term in t["any"]):
                ln, p = _first(r, TOP)
                out.append(Finding(f"P-{rd['id']}-top", "warn", ln, p,
                                   f"{who} reads the top third first; it never says: {' / '.join(t['any'])}",
                                   t.get("why", "")))
        for w in rd.get("wants", []) or []:
            if not any(term.lower() in body for term in w["any"]):
                ln, p = _first(r, ("summary",))
                out.append(Finding(f"P-{rd['id']}-wants", "error" if w.get("must") else "warn", ln, p,
                                   f"{who} looks for {' / '.join(w['any'])}; nothing on the page shows it",
                                   w.get("why", "")))
        for u in r.units_of(*TOP):
            hits = sorted({t for t in rd.get("jargon", []) or [] if re.search(r"\b" + re.escape(t), u.text, re.I)})
            if hits:
                out.append(Finding(f"P-{rd['id']}-jargon", "warn", u.line, u.path,
                                   f"{who} won't know: {', '.join(hits)} (top third)",
                                   "Say what it does for them in plain words; leave the term to Skills."))
        for a in rd.get("avoid", []) or []:
            rx = re.compile(a["pattern"], re.I)
            for u in r.units:
                m = rx.search(u.text)
                if m:
                    out.append(Finding(f"P-{rd['id']}-avoid", "warn", u.line, u.path,
                                       f"{who} would trip on '{m.group(0)}'", a.get("why", "")))
    return out


def judge_rules(rd: dict) -> list[tuple[str, tuple, str]]:
    """The reader's own judge rules, in the (id, needs, description) shape rules_llm uses."""
    return [(f"L-{rd['id']}-{i + 1:02d}", (), desc) for i, desc in enumerate(rd.get("judge", []) or [])]
