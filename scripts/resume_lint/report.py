"""Render findings as text or JSON."""
from __future__ import annotations

import json
from dataclasses import asdict

from .model import Finding

COLORS = {"error": "\033[31m", "warn": "\033[33m", "info": "\033[36m"}
RESET = "\033[0m"


def as_text(findings: list[Finding], file: str, color: bool = True, notes: list[str] = (), llm_report=None) -> str:
    lines = []
    for f in sorted(findings, key=Finding.sort_key):
        c = COLORS[f.severity] if color else ""
        r = RESET if color else ""
        tag = "llm " if f.source == "llm" else "code"
        loc = f"{file}:{f.line}" if f.line else file
        lines.append(f"{loc}: {c}{f.severity:5}{r} [{tag}] {f.rule}  {f.path}")
        lines.append(f"    {f.message}")
        if f.suggestion:
            lines.append(f"    → {f.suggestion}")
    if llm_report:
        lines.append("")
        lines.append("Whole-document read:")
        for i, t in enumerate(llm_report.top_issues, 1):
            lines.append(f"  {i}. {t}")
        lines.append(f"  Most flattering:  {llm_report.most_flattering_read}")
        lines.append(f"  Least flattering: {llm_report.least_flattering_read}")
    counts = {s: sum(1 for f in findings if f.severity == s) for s in ("error", "warn", "info")}
    lines.append("")
    lines.append(f"{len(findings)} findings: {counts['error']} error, {counts['warn']} warn, {counts['info']} info")
    for n in notes:
        lines.append(f"note: {n}")
    return "\n".join(lines)


def as_json(findings: list[Finding], llm_report=None, notes: list[str] = ()) -> str:
    payload = {"findings": [asdict(f) for f in sorted(findings, key=Finding.sort_key)], "notes": list(notes)}
    if llm_report:
        payload["whole_document"] = llm_report.model_dump()
    return json.dumps(payload, indent=2)
