"""Role-facet and specialism-facet code rules: what the role is read for, and pedigree signals."""
from __future__ import annotations

import re

from .model import Finding, Resume, strip_markdown, words
from .facets import rule


def _f(rule_id, sev, line, path, msg, sug=""):
    return Finding(rule_id, sev, line, path, msg, sug)


def _body(r: Resume) -> str:
    return strip_markdown(" ".join(u.text for u in r.units_of("highlight", "entry_summary", "summary"))).lower()


def _pubs(r: Resume) -> str:
    return " ".join(u.text for u in r.units_of("pub_title", "pub_publisher", "pub_summary")).lower()


def _first_line(r: Resume, *kinds) -> int:
    return min((u.line for u in r.units_of(*kinds)), default=0)


def _signal(r: Resume, rule_id, terms, where, sev, msg, sug, kinds=("highlight", "entry_summary", "summary")):
    text = _body(r) if where == "body" else _pubs(r)
    if not any(t in text for t in terms):
        return [_f(rule_id, sev, _first_line(r, *kinds), where, msg, sug)]
    return []


# ---------------------------------------------------------------- role: ai-scientist
@rule("ai-scientist")
def rule_sc_first_author(r: Resume):
    surname = (r.cv.get("name") or "").split(" ")[-1].lower()
    firsts = [u for u in r.units_of("pub_summary") if re.match(r"^\*\*?[^,]*" + re.escape(surname), u.text.strip(), re.I)]
    if r.units_of("pub_summary") and not firsts:
        return [_f("R-SC01-first-author", "warn", _first_line(r, "pub_title"), "Publications", "No first-author publication visible",
                   "A scientist is read for first-author work; if you have it, make sure the author order shows it.")]
    return []


@rule("ai-scientist")
def rule_sc_result_language(r: Resume):
    rx = re.compile(r"\b(showed|show|found|find|proved|prove|measured|demonstrat\w*|established|characteri[sz]ed|no evidence|result)\b", re.I)
    hl = [u for u in r.units_of("highlight") if u.entry.startswith("exp")]
    if hl and not any(rx.search(u.text) for u in hl):
        return [_f("R-SC02-results", "warn", hl[0].line, "Experience", "No experience bullet states a research result (showed, found, measured, no evidence)",
                   "A scientist's bullets should read as findings, not just activities.")]
    return []


@rule("ai-scientist")
def rule_sc_publications_present(r: Resume):
    if not r.entries("Publications"):
        return [_f("R-SC03-publications", "error", 0, "cv.sections", "No Publications section", "Scientists are screened on the publication list first.")]
    return []


# ---------------------------------------------------------------- role: research-engineer
@rule("research-engineer")
def rule_re_infra_vocab(r: Resume):
    return _signal(r, "R-RE01-infra", ("pipeline", "training", "throughput", "profil", "kernel", "distributed", "cluster", "latency", "memory"), "body", "warn",
                   "No infrastructure vocabulary in the body (pipeline, throughput, kernels, distributed, latency)",
                   "Research engineers are read for the systems that made the research run.")


@rule("research-engineer")
def rule_re_bridge(r: Resume):
    body = _body(r)
    shipped = any(t in body for t in ("shipped", "production", "deployed", "integrat"))
    research = any(t in body for t in ("paper", "published", "accepted", "neurips", "siggraph", "transactions"))
    if not (shipped and research):
        missing = "shipping" if not shipped else "research"
        return [_f("R-RE02-bridge", "warn", _first_line(r, "summary"), "body", f"The body shows research or shipping but not both (missing: {missing})",
                   "The research-engineer pitch is the bridge; evidence both ends.")]
    return []


@rule("research-engineer")
def rule_re_perf_numbers(r: Resume):
    hl = [u for u in r.units_of("highlight") if u.entry.startswith("exp")]
    perf = [u for u in hl if re.search(r"\d+\s*(%|x|ms|gb|mb|tokens|fps|gpus?|nodes?)\b", u.text, re.I)]
    if hl and not perf:
        return [_f("R-RE03-perf-numbers", "warn", hl[0].line, "Experience", "No bullet gives a performance number with a unit (%, x, ms, GB, GPUs)",
                   "Research engineers are read for measured speedups and scale.")]
    return []


# ---------------------------------------------------------------- role: engineer
@rule("engineer")
def rule_en_production(r: Resume):
    return _signal(r, "R-EN01-production", ("shipped", "production", "deployed", "users", "on-call", "reliab", "maintain"), "body", "warn",
                   "No production or shipping vocabulary in the body", "Engineers are read for what ran in production and who depended on it.")


@rule("engineer")
def rule_en_languages_evidenced(r: Resume):
    body = _body(r)
    out = []
    for gi, g in enumerate(r.entries("Skills")):
        if not re.search(r"language", g.get("label", ""), re.I):
            continue
        missing = [k for k in (g.get("keywords") or []) if re.split(r"\s*\(", k)[0].strip().lower() not in body]
        first = next((u for u in r.units if u.entry == f"skill[{gi}]"), None)
        if missing and first:
            out.append(_f("R-EN02-languages", "warn", first.line, f"Skills[{gi}]", f"Languages listed but never shown in a bullet: {', '.join(missing)}",
                          "Engineering readers test listed languages; keep the ones a bullet demonstrates."))
    return out


@rule("engineer")
def rule_en_publications_trim(r: Resume):
    n = len(r.entries("Publications"))
    if n > 3:
        return [_f("R-EN03-publications-trim", "info", _first_line(r, "pub_title"), "Publications", f"{n} publications on an engineering resume",
                   "Keep the two or three that show engineering depth; title the section 'Selected publications'.")]
    return []


# ---------------------------------------------------------------- specialism: materials-science
@rule("materials-science")
def rule_ms_venue(r: Resume):
    return _signal(r, "P-MS01-venue", ("angewandte", "npj", "digital discovery", "chemistry of materials", "nature materials", "jacs"), "pubs", "warn",
                   "No materials/chemistry venue visible in Publications", "The pedigree needs the venue names a materials reader recognises.", kinds=("pub_title",))


@rule("materials-science")
def rule_ms_methods(r: Resume):
    return _signal(r, "P-MS02-methods", ("dft", "crystal", "materials", "synthes", "vasp", "structure prediction"), "body", "info",
                   "No materials-science method vocabulary in the body", "Name the methods (DFT, crystal-structure learning, synthesis) if the reader is from the field.")


# ---------------------------------------------------------------- specialism: ml-evaluation
@rule("ml-evaluation")
def rule_ev_vocab(r: Resume):
    return _signal(r, "P-EV01-vocab", ("evaluation", "benchmark", "calibration", "confidence", "metacognition", "eval"), "body", "warn",
                   "No evaluation vocabulary in the body", "An evaluation specialist should name benchmarks, calibration, or confidence work explicitly.")


@rule("ml-evaluation", "ai-scientist")
def rule_ev_paper_visible(r: Resume):
    return _signal(r, "P-EV02-paper", ("metacognition", "calibration", "confidence", "evaluation"), "pubs", "info",
                   "No evaluation paper visible in Publications", "If the NeurIPS paper is the evaluation credential, its title should make that obvious.", kinds=("pub_title",))


# ---------------------------------------------------------------- specialism: hpc-systems
@rule("hpc-systems")
def rule_hpc_vocab(r: Resume):
    return _signal(r, "P-HPC01-vocab", ("cuda", "slurm", "deepspeed", "multi-gpu", "distributed", "cluster", "kernel", "fsdp"), "body", "warn",
                   "No HPC/distributed vocabulary in the body", "Name the stack: CUDA kernels, SLURM, DeepSpeed, node counts.")


@rule("hpc-systems")
def rule_hpc_scale_number(r: Resume):
    hl = r.units_of("highlight")
    if hl and not any(re.search(r"\d+\s*(gpus?|nodes?|billion|b\b|tokens|parameters)", u.text, re.I) for u in hl):
        return [_f("P-HPC02-scale-number", "warn", hl[0].line, "Experience", "No scale number (GPUs, nodes, parameters, tokens) anywhere",
                   "HPC pedigree without a scale number reads as a claim.")]
    return []


# ---------------------------------------------------------------- specialism: graphics
# ---------------------------------------------------------------- graphics
@rule("graphics")
def rule_gr_venue(r: Resume):
    return _signal(r, "P-GR01-venue", ("siggraph", "transactions on graphics", "tog", "egsr", "hpg", "i3d", "eurographics"), "pubs", "warn",
                   "No graphics venue named in Publications", "A graphics lead scans for SIGGRAPH/TOG; make sure it's visible.", kinds=("pub_title",))


@rule("graphics")
def rule_gr_realtime_signal(r: Resume):
    return _signal(r, "P-GR02-realtime", ("real-time", "frame", "ms", "gpu", "shader", "render"), "body", "warn",
                   "No real-time or GPU vocabulary in the body", "Graphics readers want to see frame budgets, GPU work, or rendering pipelines named.")


@rule("graphics")
def rule_gr_ml_jargon(r: Resume):
    out = []
    rx = re.compile(r"\b(self-supervised|contrastive|mutual information|infomax|tetrachoric|factor analysis|calibration|fine-tun\w*)\b", re.I)
    for u in r.units_of("highlight", "entry_summary"):
        hits = sorted({m.group(0).lower() for m in rx.finditer(u.text)})
        if hits:
            out.append(_f("P-GR03-ml-jargon", "info", u.line, u.path, f"ML term a graphics reader may skip: {', '.join(hits)}",
                          "Keep it, but lead the bullet with what it achieved in graphics terms."))
    return out

RULES = [v for k, v in sorted(globals().items()) if k.startswith("rule_")]
