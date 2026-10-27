"""Shared data model: findings, and the resume flattened into lintable units."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

SEVERITIES = ("error", "warn", "info")


@dataclass
class Finding:
    rule: str
    severity: str
    line: int
    path: str
    message: str
    suggestion: str = ""
    source: str = "code"  # "code" or "llm"

    def sort_key(self):
        return (SEVERITIES.index(self.severity), self.line, self.rule)


@dataclass
class Unit:
    """One lintable piece of text with its YAML path and line number."""
    id: str            # e.g. "exp[0].hl[2]"
    kind: str          # summary | label | highlight | entry_summary | pub_title | pub_summary | pub_publisher | keyword | interest
    path: str          # human-readable YAML path
    text: str
    line: int
    entry: str = ""    # owning entry id, e.g. "exp[0]"
    meta: dict = field(default_factory=dict)


@dataclass
class Resume:
    file: Path
    raw: str
    lines: list[str]
    cv: dict
    units: list[Unit]
    pdf: Path | None = None

    def units_of(self, *kinds: str) -> list[Unit]:
        return [u for u in self.units if u.kind in kinds]

    def entries(self, section: str) -> list[dict]:
        return (self.cv.get("sections", {}) or {}).get(section, []) or []


def _find_line(lines: list[str], needle: str, start: int = 0) -> int:
    """1-indexed line of the first line at/after `start` containing the start of `needle`."""
    probe = needle.strip().split("\n")[0][:60]
    for i in range(start, len(lines)):
        if probe and probe in lines[i]:
            return i + 1
    return 0


def load(path: Path, pdf: Path | None = None) -> Resume:
    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    data = yaml.safe_load(raw) or {}
    cv = data.get("cv", {}) or {}
    units: list[Unit] = []
    cursor = 0  # advance through the file so repeated strings map to the right line

    def add(id_, kind, path_, text, entry="", **meta):
        nonlocal cursor
        if not isinstance(text, str) or not text.strip():
            return
        ln = _find_line(lines, text, cursor)
        if ln:
            cursor = ln - 1
        units.append(Unit(id_, kind, path_, text.strip(), ln, entry, meta))

    add("name", "name", "cv.name", cv.get("name", ""))
    add("label", "label", "cv.label", cv.get("label", ""))
    add("summary", "summary", "cv.summary", cv.get("summary", ""))

    sections = cv.get("sections", {}) or {}
    for si, entry in enumerate(sections.get("Experience", []) or []):
        eid = f"exp[{si}]"
        add(f"{eid}.summary", "entry_summary", f"Experience[{si}].summary", entry.get("summary", ""), eid,
            company=entry.get("company", ""), current=(str(entry.get("end_date", "")).lower() == "present"))
        for hi, h in enumerate(entry.get("highlights", []) or []):
            add(f"{eid}.hl[{hi}]", "highlight", f"Experience[{si}].highlights[{hi}]", h, eid,
                company=entry.get("company", ""), current=(str(entry.get("end_date", "")).lower() == "present"))
    for si, entry in enumerate(sections.get("Education", []) or []):
        eid = f"edu[{si}]"
        for hi, h in enumerate(entry.get("highlights", []) or []):
            add(f"{eid}.hl[{hi}]", "highlight", f"Education[{si}].highlights[{hi}]", h, eid,
                company=entry.get("institution", ""), current=False)
    for pi, pub in enumerate(sections.get("Publications", []) or []):
        eid = f"pub[{pi}]"
        add(f"{eid}.title", "pub_title", f"Publications[{pi}].title", pub.get("title", ""), eid)
        add(f"{eid}.summary", "pub_summary", f"Publications[{pi}].summary", pub.get("summary", ""), eid)
        add(f"{eid}.publisher", "pub_publisher", f"Publications[{pi}].publisher", pub.get("publisher", ""), eid)
    for gi, group in enumerate(sections.get("Skills", []) or []):
        for ki, kw in enumerate(group.get("keywords", []) or []):
            add(f"skill[{gi}][{ki}]", "keyword", f"Skills[{gi}].keywords[{ki}]", kw, f"skill[{gi}]",
                group=group.get("label", ""))
    for gi, group in enumerate(sections.get("Interests", []) or []):
        for ki, kw in enumerate(group.get("keywords", []) or []):
            add(f"interest[{gi}][{ki}]", "interest", f"Interests[{gi}].keywords[{ki}]", kw, f"interest[{gi}]")

    if pdf is None:
        pdf = path.parent.parent / "assets" / "resume" / "resume.pdf"
    return Resume(path, raw, lines, cv, units, pdf)


WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’\-\+\#\.]*")


def words(text: str) -> list[str]:
    return WORD_RE.findall(text)


def strip_markdown(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text.replace("**", "").replace("*", "")
