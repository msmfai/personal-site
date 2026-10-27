"""Facets: orthogonal axes a resume version is composed from. Rules tag facet values.

A profile is a *set* of facet values, e.g. {role:research-engineer, specialism:graphics,
audience:frontier-lab}. Base facets are always on. Named presets are sugar for common sets.
Rules declare what they need: a single value, a list (any of), or a tuple (all of).
"""
from __future__ import annotations

# axis -> {value: description}
AXES: dict[str, dict[str, str]] = {
    "base": {
        "universal": "Any resume in any field: mechanics, dates, duplicates, hedging, length.",
        "technical": "Technical resumes: acronyms, jargon, skills lists, metrics.",
    },
    "role": {
        "ai-scientist":      "Produces research: papers, results, methods. Read for contribution and rigor.",
        "research-engineer": "Turns research into running systems. Read for infrastructure, throughput, shipped research.",
        "engineer":          "Ships production software. Read for ownership, reliability, scope.",
    },
    "specialism": {
        "graphics":          "Pedigree in rendering / real-time graphics (SIGGRAPH, TOG).",
        "materials-science": "Pedigree in materials informatics / computational chemistry.",
        "ml-evaluation":     "Pedigree in evaluation, benchmarks, calibration, metacognition.",
        "hpc-systems":       "Pedigree in distributed training, CUDA, cluster-scale compute.",
    },
    "audience": {
        "frontier-lab": "Research lead at a frontier AI lab.",
        "big-tech":     "Hiring manager at a large technology company.",
        "academia":     "Professor or committee screening research applications.",
        "buyer":        "CTO or head of research deciding whether to hire a consultant.",
        "investor":     "Seed investor or prospective cofounder.",
        "trading-firm": "Quantitative research hiring manager at a trading firm.",
    },
}
BASE = ("universal", "technical")
ALL_VALUES = {v: axis for axis, vals in AXES.items() for v in vals}

ROLE_NAME = {"ai-scientist": "an AI research scientist", "research-engineer": "a research engineer", "engineer": "a software engineer"}
AUDIENCE_PERSONA = {
    "frontier-lab": "a research lead at a frontier AI lab (DeepMind, Anthropic, OpenAI tier), deciding whether to phone-screen",
    "big-tech":     "a hiring manager at a large technology company",
    "academia":     "a professor screening postdoc and research applications",
    "buyer":        "a CTO or head of research deciding whether to engage this person as a consultant",
    "investor":     "a seed investor or prospective cofounder assessing whether this person can build and ship independently",
    "trading-firm": "a quantitative research hiring manager at a trading firm (Jane Street, Two Sigma tier)",
}

PRESETS: dict[str, set[str]] = {
    "ai-lab-scientist":  {"ai-scientist", "frontier-lab"},
    "ai-lab-re":         {"research-engineer", "frontier-lab", "hpc-systems"},
    "graphics-re":       {"research-engineer", "graphics", "big-tech"},
    "graphics-scientist": {"ai-scientist", "graphics", "big-tech"},
    "engineer":          {"engineer", "big-tech"},
    "academic":          {"ai-scientist", "academia"},
    "consulting":        {"ai-scientist", "ml-evaluation", "buyer"},
    "quant":             {"research-engineer", "trading-firm"},
    "founder":           {"engineer", "investor"},
    "all":               set(ALL_VALUES),
}
DEFAULT_PRESET = "ai-lab-scientist"


def rule(*needs):
    """Decorator. rule("x") needs x; rule("x", "y") needs x AND y; rule(["x", "y"]) needs x OR y."""
    flat = [n for need in needs for n in (need if isinstance(need, list) else [need])]
    for n in flat:
        if n not in ALL_VALUES:
            raise ValueError(f"unknown facet value {n!r}")

    def deco(fn):
        fn.needs = needs
        return fn
    return deco


def resolve(preset: str | None, facets: list[str]) -> set[str]:
    """Compose the active facet set from a preset (optional) plus explicit facet values."""
    active = set(BASE)
    if preset:
        if preset not in PRESETS:
            raise KeyError(f"unknown preset {preset!r}; choose from {', '.join(PRESETS)}")
        active |= PRESETS[preset]
    for f in facets:
        v = f.split(":", 1)[-1]
        if v not in ALL_VALUES:
            raise KeyError(f"unknown facet value {v!r}; see --list-rules")
        active.add(v)
    return active


def is_active(needs, active: set[str]) -> bool:
    if not needs:
        return True
    for need in needs:  # tuple elements are AND-ed
        if isinstance(need, list):
            if not any(n in active for n in need):
                return False
        elif need not in active:
            return False
    return True


def select(rules, active: set[str]):
    return [r for r in rules if is_active(getattr(r, "needs", ()), active)]


def persona(active: set[str]) -> str:
    audience = next((a for a in AUDIENCE_PERSONA if a in active), None)
    role = next((r for r in ROLE_NAME if r in active), None)
    specs = [s for s in AXES["specialism"] if s in active]
    who = AUDIENCE_PERSONA.get(audience, "an experienced technical recruiter")
    if role:
        who += f", hiring for {ROLE_NAME[role]} role"
    if specs:
        who += f", who knows the {', '.join(specs)} field(s) well"
    return who


def describe(active: set[str]) -> str:
    parts = []
    for axis, vals in AXES.items():
        chosen = [v for v in vals if v in active]
        if chosen and axis != "base":
            parts.append(f"{axis}: {', '.join(chosen)}")
    return "; ".join(parts) or "base only"
