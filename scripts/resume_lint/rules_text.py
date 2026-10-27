"""Deterministic per-unit text rules. Each rule: (resume) -> list[Finding]."""
from __future__ import annotations

import re
from collections import Counter

from .facets import rule
from .model import Finding, Resume, Unit, strip_markdown, words

PROSE_KINDS = ("summary", "entry_summary", "highlight", "pub_summary")
BULLET_KINDS = ("highlight",)

WEAK_OPENERS = r"^(worked|helped|assisted|responsible|involved|participated|supported|contributed|tasked|duties|utilized|utilised)\b"
HEDGES = r"\b(just|kind of|sort of|somewhat|fairly|quite|a bit|arguably|basically|essentially|relatively|approximately|roughly|around|about)\b"
BUZZWORDS = r"\b(leverag\w*|synerg\w*|cutting[- ]edge|state[- ]of[- ]the[- ]art|passionate|results[- ]driven|dynamic|innovative|world[- ]class|best[- ]in[- ]class|seamless\w*|robust|thought leader\w*|guru|ninja|rockstar|disruptive|game[- ]chang\w*|next[- ]gen\w*|holistic|impactful)\b"
CLICHES = r"(particularly interested in|proven track record|team player|detail[- ]oriented|self[- ]starter|fast learner|hit the ground running|go[- ]getter|think outside the box|wear many hats|hard[- ]working|strong communication skills)"
VAGUE_QTY = r"\b(multiple|numerous|many|several|various|significant\w*|substantial\w*|a number of|a range of|wide range)\b"
EXAGGERATION = r"\b(world'?s (first|best|only)|first[- ]ever|revolutionary|unprecedented|expert in|mastery of|unparalleled|groundbreaking)\b"
FILLER_ADVERBS = r"\b(successfully|effectively|efficiently|actively|highly|very|really|extremely|truly|deeply|greatly)\b"
SELF_DIMINISHING = r"\b(only|merely|small|minor|attempted|tried to|some experience|basic|simple)\b"
STALE_STATUS = r"\b(conditionally|pending|under review|submitted to|in preparation|forthcoming|to appear|in press)\b"
PASSIVE = r"\b(was|were|been|being|is|are|be)\s+(\w+ed|built|made|done|given|shown|taken|written|led|run|held)\b"
FIRST_PERSON = r"\b(I|me|my|mine|we|our)\b"
PRESENT_VERBS = {"design", "lead", "build", "develop", "run", "manage", "maintain", "own", "drive", "work", "create", "write", "research", "advise", "ship", "deliver"}

ACRONYM_ALLOW = {
    "AI", "ML", "LLM", "LLMS", "GPU", "GPUS", "CPU", "API", "APIS", "PHD", "UK", "USA", "US", "AAA", "HPC", "NLP",
    "CUDA", "SQL", "HTML", "CSS", "JSON", "YAML", "PDF", "CV", "IO", "AWS", "GCP", "IDE", "OS", "GAN", "GANS",
    "VAE", "VAES", "ACM", "IEEE", "NES", "RPG", "SEED", "GPT", "GLSL", "HLSL", "JAX", "ONNX", "SLURM", "MLOPS",
    "ML", "II", "III", "MSC", "BSC", "MPHYS", "NEURIPS", "SIGGRAPH", "TOG", "ID", "MATLAB", "CLI", "NES", "RPG", "VAES",
}


def _flag(u: Unit, rule: str, sev: str, msg: str, sug: str = "") -> Finding:
    return Finding(rule, sev, u.line, u.path, msg, sug)


def _regex_rule(units, pattern, rule, sev, label, suggestion, flags=re.I):
    out = []
    rx = re.compile(pattern, flags)
    for u in units:
        hits = sorted({m.group(0).lower() for m in rx.finditer(strip_markdown(u.text))})
        if hits:
            out.append(_flag(u, rule, sev, f"{label}: {', '.join(hits)}", suggestion))
    return out


@rule("universal")
def rule_weak_opener(r: Resume):
    return _regex_rule(r.units_of(*BULLET_KINDS), WEAK_OPENERS, "T01-weak-opener", "warn",
                       "Bullet opens with a weak verb", "Open with the concrete action: Designed, Built, Reduced, Shipped, Proved.")


@rule("universal")
def rule_hedges(r: Resume):
    return _regex_rule(r.units_of(*PROSE_KINDS), HEDGES, "T02-hedge", "warn",
                       "Hedging language", "Delete the hedge or replace it with a number.")


@rule("universal")
def rule_buzzwords(r: Resume):
    return _regex_rule(r.units_of(*PROSE_KINDS, "label"), BUZZWORDS, "T03-buzzword", "warn",
                       "Buzzword", "Replace with what was actually done or measured.")


@rule("universal")
def rule_cliches(r: Resume):
    return _regex_rule(r.units_of(*PROSE_KINDS), CLICHES, "T04-cliche", "info",
                       "Resume cliché", "Cut it, or replace with a specific example that shows the trait.")


@rule("universal")
def rule_vague_quantifiers(r: Resume):
    out = []
    rx = re.compile(VAGUE_QTY, re.I)
    for u in r.units_of(*PROSE_KINDS):
        for m in rx.finditer(u.text):
            tail = u.text[m.end():m.end() + 12]
            if not re.match(r"\s*\d", tail):
                out.append(_flag(u, "T05-vague-quantity", "warn", f"Vague quantifier: '{m.group(0)}'",
                                 "Give the number, or drop the word."))
                break
    return out


@rule("technical")
def rule_no_number(r: Resume):
    out = []
    for u in r.units_of("highlight"):
        if u.entry.startswith("exp") and len(words(u.text)) > 15 and not re.search(r"\d", u.text):
            out.append(_flag(u, "T06-no-metric", "info", "Long experience bullet with no number in it",
                             "If there is a measurable outcome (speed, size, count, cost, time), state it."))
    return out


@rule("universal")
def rule_length(r: Resume):
    out = []
    for u in r.units_of("highlight", "entry_summary"):
        n = len(words(u.text))
        if n > 40:
            out.append(_flag(u, "T07-too-long", "warn", f"Bullet is {n} words", "Split into two bullets or cut to one claim."))
        elif u.kind == "highlight" and n < 5:
            out.append(_flag(u, "T08-too-short", "info", f"Bullet is only {n} words", "Say what it was for or what it produced."))
    return out


@rule("universal")
def rule_passive(r: Resume):
    return _regex_rule(r.units_of(*PROSE_KINDS), PASSIVE, "T09-passive", "info",
                       "Possible passive voice", "Prefer active voice so the reader sees you as the agent.")


@rule(["big-tech", "frontier-lab", "trading-firm"])
def rule_first_person(r: Resume):
    out = _regex_rule(r.units_of("highlight", "entry_summary"), FIRST_PERSON, "T10-first-person", "warn",
                      "First-person pronoun in a bullet", "Bullets are implicitly first person; drop the pronoun.", flags=0)
    for u in r.units_of("summary"):
        if re.search(FIRST_PERSON, u.text):
            out.append(_flag(u, "T10-first-person", "info", "Summary is written in the first person",
                             "Style choice. Quant and research resumes usually use an impersonal summary."))
    return out


@rule("universal")
def rule_tense_mix(r: Resume):
    out = []
    by_entry: dict[str, list[Unit]] = {}
    for u in r.units_of("highlight"):
        by_entry.setdefault(u.entry, []).append(u)
    for entry, us in by_entry.items():
        past = [u for u in us if re.match(r"^\w+ed\b", u.text)]
        present = [u for u in us if u.text.split(" ")[0].lower() in PRESENT_VERBS]
        if past and present:
            for u in present:
                out.append(_flag(u, "T11-tense-mix", "warn", "Present-tense opener in an entry whose other bullets are past tense",
                                 "Use one tense per entry."))
    return out


@rule("universal")
def rule_repeated_opener(r: Resume):
    out = []
    by_section: dict[str, list[Unit]] = {}
    for u in r.units_of("highlight"):
        by_section.setdefault(u.entry.split("[")[0], []).append(u)
    for sec, us in by_section.items():
        counts = Counter(u.text.split(" ")[0].lower() for u in us)
        for word, n in counts.items():
            if n >= 3:
                first = next(u for u in us if u.text.split(" ")[0].lower() == word)
                out.append(_flag(first, "T12-repeated-opener", "info", f"'{word.capitalize()}' opens {n} bullets in this section",
                                 "Vary the verbs so each bullet reads as a distinct achievement."))
    return out


@rule("universal")
def rule_punctuation(r: Resume):
    out = []
    checks = [(r"  +", "double space"), (r"\s,", "space before comma"), (r"\.\.(?!\.)", "double period"),
              (r"et al\.\.", "'et al..'"), (r"\s$", "trailing whitespace"), (r"\(\s|\s\)", "space inside parenthesis")]
    for u in r.units:
        for rx, label in checks:
            if re.search(rx, u.text):
                out.append(_flag(u, "T13-punctuation", "warn", f"Punctuation: {label}"))
    by_entry: dict[str, list[Unit]] = {}
    for u in r.units_of("highlight"):
        by_entry.setdefault(u.entry, []).append(u)
    for entry, us in by_entry.items():
        ends = {u.text.rstrip().endswith(".") for u in us}
        if len(ends) == 2:
            odd = [u for u in us if u.text.rstrip().endswith(".")]
            out.append(_flag(odd[0], "T13-punctuation", "warn", "Mixed terminal periods across bullets in this entry",
                             "Pick one convention for every bullet."))
    return out


@rule("technical")
def rule_acronyms(r: Resume):
    out = []
    full = strip_markdown(r.raw)
    expanded = set(m.group(1).upper() for m in re.finditer(r"\(([A-Z][A-Za-z]{1,6})\)", full))
    expanded |= set(m.group(1).upper() for m in re.finditer(r"\b([A-Z]{2,6})\s*\(", full))
    seen = set()
    for u in r.units_of(*PROSE_KINDS, "keyword"):
        for tok in re.findall(r"\b[A-Z]{2,6}\b", strip_markdown(u.text)):
            if tok in ACRONYM_ALLOW or tok in expanded or tok in seen:
                continue
            seen.add(tok)
            out.append(_flag(u, "T14-acronym", "info", f"Acronym '{tok}' is never expanded",
                             "Expand on first use if a general ML reader might not know it."))
    return out


@rule("universal")
def rule_sentence_length(r: Resume):
    out = []
    for u in r.units_of("summary", "entry_summary"):
        for s in re.split(r"(?<=[.!?])\s+", strip_markdown(u.text)):
            n = len(words(s))
            if n > 35:
                out.append(_flag(u, "T15-long-sentence", "warn", f"Sentence of {n} words: '{s[:50]}…'", "Split it."))
    return out


@rule("technical")
def rule_jargon_density(r: Resume):
    out = []
    for u in r.units_of("highlight", "entry_summary"):
        ws = words(strip_markdown(u.text))
        if len(ws) < 8:
            continue
        tech = [w for w in ws if re.match(r"^[A-Z]{2,}|^[A-Z][a-z]+[A-Z]|^\w+[-/]\w+$", w)]
        ratio = len(tech) / len(ws)
        if ratio > 0.3:
            out.append(_flag(u, "T16-jargon-density", "info", f"{int(ratio * 100)}% of words are technical tokens or acronyms",
                             "Fine for a specialist reader; consider one plain-English clause for everyone else."))
    return out


@rule("universal")
def rule_stale_status(r: Resume):
    return _regex_rule(r.units, STALE_STATUS, "T17-stale-status", "warn",
                       "Status word that goes stale", "Re-check this is still true, then remove the qualifier once it isn't needed.")


@rule("universal")
def rule_self_diminishing(r: Resume):
    return _regex_rule(r.units_of("highlight", "summary"), SELF_DIMINISHING, "T18-self-diminishing", "info",
                       "Self-diminishing word", "Check whether it undersells the work.")


@rule("universal")
def rule_markdown_artifacts(r: Resume):
    out = []
    for u in r.units:
        if u.text.count("**") % 2 or u.text.count("(") != u.text.count(")") or u.text.count("[") != u.text.count("]"):
            out.append(_flag(u, "T20-markup", "error", "Unbalanced bold markers or brackets"))
        if u.kind in ("highlight", "entry_summary") and re.search(r"https?://", u.text):
            out.append(_flag(u, "T20-markup", "info", "Raw URL in a bullet", "Link the phrase instead, or drop the URL from the PDF."))
    return out


@rule("universal")
def rule_exaggeration(r: Resume):
    return _regex_rule(r.units_of(*PROSE_KINDS, "label"), EXAGGERATION, "T21-exaggeration", "warn",
                       "Overclaim", "Replace with the verifiable fact.")


@rule("universal")
def rule_filler_adverbs(r: Resume):
    return _regex_rule(r.units_of(*PROSE_KINDS), FILLER_ADVERBS, "T22-filler-adverb", "info",
                       "Filler adverb", "Delete it; the verb should carry the weight.")


RULES = [v for k, v in sorted(globals().items()) if k.startswith("rule_")]
