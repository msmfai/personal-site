"""Audience-facet code rules: what a particular reader screens for."""
from __future__ import annotations

import re

from .model import Finding, Resume, strip_markdown, words
from .facets import rule


def _f(rule_id, sev, line, path, msg, sug=""):
    return Finding(rule_id, sev, line, path, msg, sug)


def _body(r: Resume) -> str:
    return strip_markdown(" ".join(u.text for u in r.units_of("highlight", "entry_summary", "summary"))).lower()


def _pubs(r: Resume) -> str:
    return " ".join(u.text for u in r.units_of("pub_title", "pub_publisher")).lower()


def _first_line(r: Resume, *kinds) -> int:
    return min((u.line for u in r.units_of(*kinds)), default=0)


def _signal(r: Resume, rule_id, terms, where, sev, msg, sug, kinds=("highlight", "entry_summary", "summary")):
    text = _body(r) if where == "body" else _pubs(r)
    if not any(t in text for t in terms):
        return [_f(rule_id, sev, _first_line(r, *kinds), where, msg, sug)]
    return []


# ---------------------------------------------------------------- ai-lab
@rule("frontier-lab")
def rule_ai_ml_venue(r: Resume):
    return _signal(r, "D-AI01-ml-venue", ("neurips", "icml", "iclr", "acl", "cvpr", "aistats", "colm", "tmlr"), "pubs", "warn",
                   "No top ML venue named in Publications", "An AI-lab reader scans for NeurIPS/ICML/ICLR first; put the ML paper where the eye lands.",
                   kinds=("pub_title",))


@rule("frontier-lab")
def rule_ai_scale_signal(r: Resume):
    return _signal(r, "D-AI02-scale", ("distributed", "multi-gpu", "cluster", "billion", "parameters", "tokens", "pretrain", "fine-tun", "deepspeed", "fsdp"), "body", "warn",
                   "No evidence of working at scale (distributed training, model size, token counts)",
                   "The first thing a lab lead probes is compute experience; if you have it, say it with a number.")


@rule("frontier-lab")
def rule_ai_games_jargon(r: Resume):
    out = []
    rx = re.compile(r"\b(frostbite|aaa|frame[- ]time|frame budget|shader|hlsl|glsl|register pressure|alu|draw call)\b", re.I)
    for u in r.units_of("highlight", "entry_summary", "summary"):
        hits = sorted({m.group(0).lower() for m in rx.finditer(u.text)})
        if hits and not re.search(r"\((?:[^)]*\b(i\.e\.|that is|real-time|milliseconds|ms)\b[^)]*)\)", u.text, re.I):
            out.append(_f("D-AI03-games-jargon", "info", u.line, u.path, f"Games-industry term an ML reader may not weight: {', '.join(hits)}",
                          "Translate into the ML reader's units (latency, memory, throughput) or gloss it once."))
    return out


@rule("frontier-lab")
def rule_ai_eval_signal(r: Resume):
    return _signal(r, "D-AI04-evaluation", ("evaluation", "benchmark", "calibration", "eval"), "body", "info",
                   "No evaluation or benchmark work named in the body", "Labs are hiring for evaluation; if the consultancy work is that, name it as such.")


# ---------------------------------------------------------------- consulting
@rule("buyer")
def rule_co_client_outcomes(r: Resume):
    out = []
    rx = re.compile(r"\b(clients?|engagements?|deliver\w*|stakeholders?|labs?|customers?|for [A-Z]\w+)\b", re.I)
    for e_idx, e in enumerate(r.entries("Experience")):
        if not re.search(r"consult", (e.get("company", "") + e.get("position", "")), re.I):
            continue
        for u in r.units:
            if u.entry == f"exp[{e_idx}]" and u.kind == "highlight" and not rx.search(u.text):
                out.append(_f("D-CO01-client-outcome", "warn", u.line, u.path, "Consultancy bullet names no client, engagement, or delivered outcome",
                              "A buyer wants to see who you did it for and what they got."))
    return out


@rule("buyer")
def rule_co_academic_register(r: Resume):
    out = []
    for u in r.units_of("highlight", "entry_summary"):
        ws = words(strip_markdown(u.text))
        tech = [w for w in ws if re.match(r"^[A-Z]{2,}|^[A-Z][a-z]+[A-Z]|^\w+[-/]\w+$", w)]
        if len(ws) >= 8 and len(tech) / len(ws) > 0.3:
            out.append(_f("D-CO02-register", "warn", u.line, u.path, "Dense technical register for a buyer who may not be a specialist",
                          "Lead with the business outcome, keep one technical clause for credibility."))
    return out


@rule("buyer")
def rule_co_availability(r: Resume):
    return _signal(r, "D-CO03-availability", ("engagement", "available", "open to", "get in touch", "contact"), "body", "info",
                   "Nothing tells a buyer you're available or how to engage", "One line on the kind of engagements you take.", kinds=("summary",))


# ---------------------------------------------------------------- quant
@rule("trading-firm")
def rule_qu_impersonal_summary(r: Resume):
    return [_f("D-QU01-impersonal", "warn", u.line, u.path, "Summary is in the first person",
               "Quant resumes use an impersonal summary: 'Research scientist working on…'")
            for u in r.units_of("summary") if re.search(r"\b(I|my|me)\b", u.text)]


@rule("trading-firm")
def rule_qu_honorific(r: Resume):
    return [_f("D-QU02-honorific", "warn", u.line, u.path, "Honorific in the name line", "Quant firms read 'Dr.' as a tell; bare name.")
            for u in r.units_of("name") if re.match(r"^(Dr|Prof)\.?\s", u.text)]


@rule("trading-firm")
def rule_qu_math_signal(r: Resume):
    return _signal(r, "D-QU03-maths", ("probabil", "statistic", "optimi", "linear algebra", "stochastic", "bayesian", "factor analysis", "regression", "estimat"), "body", "warn",
                   "No probability, statistics, or optimisation vocabulary in the body", "Quant readers screen for mathematical maturity; name the methods.")


@rule("trading-firm")
def rule_qu_metric_density(r: Resume):
    hl = [u for u in r.units_of("highlight") if u.entry.startswith("exp")]
    if not hl:
        return []
    with_num = sum(1 for u in hl if re.search(r"\d", u.text))
    if with_num / len(hl) < 0.5:
        return [_f("D-QU04-metric-density", "warn", hl[0].line, "Experience", f"Only {with_num} of {len(hl)} experience bullets contain a number",
                   "Quant readers weight quantified outcomes; aim for most bullets.")]
    return []


# ---------------------------------------------------------------- founder
@rule("investor")
def rule_fo_traction(r: Resume):
    out = []
    rx = re.compile(r"\b(revenue|customers?|users?|clients?|raised|arr|mrr|grew|growth|\d+\s*(?:\w+\s+)?(experts?|people|engineers|contributors|labs?))\b", re.I)
    for e_idx, e in enumerate(r.entries("Experience")):
        if not re.search(r"\b(founder|founded|ceo|cto|co-?founder|principal)\b", (e.get("company", "") + " " + e.get("position", "")), re.I):
            continue
        us = [u for u in r.units if u.entry == f"exp[{e_idx}]" and u.kind == "highlight"]
        if us and not any(rx.search(u.text) for u in us):
            out.append(_f("D-FO01-traction", "warn", us[0].line, f"Experience[{e_idx}]", "Founder entry has no traction number (customers, revenue, people, growth)",
                          "Investors read the founder entry for numbers first."))
    return out


@rule("investor")
def rule_fo_ownership_verbs(r: Resume):
    out = []
    for u in r.units_of("highlight"):
        if re.match(r"^(assisted|supported|contributed|participated|helped)\b", u.text, re.I):
            out.append(_f("D-FO02-ownership", "warn", u.line, u.path, "Bullet reads as a contributor, not an owner", "Founders are read for agency: Founded, Built, Shipped, Grew."))
    return out


RULES = [v for k, v in sorted(globals().items()) if k.startswith("rule_")]
