"""Tells of AI authorship beyond the stock-verb list in rules_slop, with Claude's own habits first.

Each rule targets a construction that models (Claude especially) overproduce and that readers have
learned to spot: the "not X, but Y" reframe, the colon reveal, the punchy "so X stops being Y"
closer, the rhetorical set-up, reflexive triads, and a house vocabulary (genuinely, actually,
crucially, landscape, nuanced…). One instance is a judgement call; a pattern is a signature.
"""
from __future__ import annotations

import re

from .facets import rule
from .model import Finding, Resume, strip_markdown

PROSE = ("label", "summary", "entry_summary", "highlight", "pub_summary")

# Words and phrases Claude reaches for far more than people writing about themselves do.
CLAUDE_WORDS = (r"\b(genuine(ly)?|actually|truly|crucial(ly)?|notabl[ey]|seamless(ly)?|robust(ly|ness)?|landscape|nuanced?|"
                r"holistic(ally)?|navigat\w+|ever[- ]evolving|rapidly evolving|deep[- ]dive|game[- ]chang\w+|transformative|"
                r"unlock\w*|realm|paradigm|journey|vibrant|rich(ly)?|thoughtful(ly)?|meaningful(ly)?|impactful|"
                r"cutting[- ]edge|world[- ]class|state[- ]of[- ]the[- ]art|best[- ]in[- ]class|ensur\w+|crafted?|"
                r"it'?s worth noting|in today'?s|at the intersection of|where \w+ meets \w+|bridg\w+ the gap)\b")

# "not just X, but Y" / "isn't X — it's Y" / "not X; Y": the reframe.
REFRAME = (r"\b(not|isn'?t|wasn'?t|aren'?t|never)\s+(just|only|merely|simply|about)\b[^.;:]{1,80}?(\bbut\b|\bit'?s\b|\bit is\b|—|;)"
           r"|\bnot only\b[^.]{1,80}\bbut also\b|\bless about\b[^.]{1,60}\bmore about\b")

# ", not Y" clipped contrast tacked onto a clause ("on GPUs it owns, not APIs").
CLIPPED_CONTRAST = r",\s+not\s+(a |an |the |just )?\w+"

# Rhetorical set-ups and framing devices.
SETUP = (r"\b(a question every \w+|the (real|key|hard) (question|problem|challenge) is|here'?s the thing|"
         r"the truth is|make no mistake|what (really )?matters is|the key is|the answer is|the result\??:|"
         r"in other words|put simply|simply put|that'?s (why|where|what))\b")

# Punchy consequence closers: ", so verification stops being the bottleneck".
CLOSER = r"\bso (that )?[\w\s-]{1,40}?\b(stops|no longer|ceases|becomes|turns into|is never)\b"

# A colon that sets up a reveal inside running prose ("…to AI: evaluations that…").
COLON_REVEAL = r"\b[A-Za-z][\w\s'-]{2,60}:\s+[a-z]"

# Serial triads: "A, B, and C".
TRIAD = r"\b[\w'-]+(?: [\w'-]+){0,3}, [\w'-]+(?: [\w'-]+){0,3}, (and|or) [\w'-]+"


def _f(rule_id, sev, u, msg, sug=""):
    return Finding(rule_id, sev, u.line, u.path, msg, sug)


def _prose(r: Resume):
    return [(u, strip_markdown(u.text)) for u in r.units_of(*PROSE)]


@rule("universal")
def rule_claude_words(r: Resume):
    rx = re.compile(CLAUDE_WORDS, re.I)
    out = []
    for u, t in _prose(r):
        hits = sorted({m.group(0).lower() for m in rx.finditer(t)})
        if hits:
            out.append(_f("T30-ai-vocab", "warn", u, f"Model-favourite word(s): {', '.join(hits)}",
                          "Cut the word or use the plain, specific one; 'actually', 'genuinely', 'crucially' add nothing a reader can check."))
    return out


@rule("universal")
def rule_reframe(r: Resume):
    rx = re.compile(REFRAME, re.I)
    return [_f("T31-reframe", "warn", u, f"'Not X, but Y' reframe: '{rx.search(t).group(0)[:60]}'",
               "State Y directly. The set-up against a straw X is the most recognisable model construction.")
            for u, t in _prose(r) if rx.search(t)]


@rule("universal")
def rule_clipped_contrast(r: Resume):
    rx = re.compile(CLIPPED_CONTRAST, re.I)
    return [_f("T32-clipped-contrast", "info", u, f"Tacked-on contrast: '{rx.search(t).group(0).strip()}'",
               "Drop the ', not Y' tail unless the contrast is the point.")
            for u, t in _prose(r) if rx.search(t)]


@rule("universal")
def rule_setup(r: Resume):
    rx = re.compile(SETUP, re.I)
    return [_f("T33-rhetorical-setup", "warn", u, f"Rhetorical set-up: '{rx.search(t).group(0)}'",
               "A résumé states what happened. Cut the framing and keep the fact.")
            for u, t in _prose(r) if rx.search(t)]


@rule("universal")
def rule_closer(r: Resume):
    rx = re.compile(CLOSER, re.I)
    return [_f("T34-punchy-closer", "warn", u, f"Punchy consequence closer: '{rx.search(t).group(0)}'",
               "End on the fact or the number, not a slogan about what it means.")
            for u, t in _prose(r) if rx.search(t)]


@rule("universal")
def rule_colon_reveal(r: Resume):
    rx = re.compile(COLON_REVEAL)
    hits = [(u, t) for u, t in _prose(r) if u.kind != "pub_summary" and rx.search(t)]
    if len(hits) < 2:  # one colon is punctuation; a habit is a signature
        return []
    return [_f("T35-colon-reveal", "warn", u, f"Colon set-up/reveal ({len(hits)} on the page): '{rx.search(t).group(0)[:50]}…'",
               "Rewrite as one plain sentence; repeated 'Label: explanation' reads as generated.")
            for u, t in hits]


@rule("universal")
def rule_triads(r: Resume):
    rx = re.compile(TRIAD, re.I)
    hits = [(u, t) for u, t in _prose(r) if rx.search(t)]
    prose = _prose(r)
    if len(hits) < 3 or len(hits) < 0.3 * len(prose):
        return []
    return [_f("T36-triad", "info", u, f"Serial triad ({len(hits)} of {len(prose)} units): '{rx.search(t).group(0)[:60]}'",
               "Models list in threes by reflex. Keep the triad only where there really are three things; otherwise two, or four.")
            for u, t in hits]


@rule("universal")
def rule_semicolon_habit(r: Resume):
    units = [(u, t) for u, t in _prose(r) if ";" in t]
    if len(units) < 2:
        return []
    return [_f("T37-semicolons", "info", u, f"Semicolon used in {len(units)} units",
               "Semicolons in self-descriptions read as model prose; use a full stop.")
            for u, _ in units]


# Vague connective phrases that gesture at a source of authority without saying anything checkable.
VAGUE_SOURCE = (r"\b(drawing on|drawn from|grounded in|rooted in|informed by|underpinned by|"
                r"(the )?(current|latest|cutting[- ]edge) (literature|research|methods|techniques)|state of the art)\b")


@rule("universal")
def rule_vague_source(r: Resume):
    rx = re.compile(VAGUE_SOURCE, re.I)
    return [_f("T38-vague-source", "warn", u, f"Gestures at authority without content: '{rx.search(t).group(0)}'",
               "Say the specific thing you did, or cut the phrase.")
            for u, t in _prose(r) if rx.search(t)]


@rule("universal")
def rule_summary_colon_list(r: Resume):
    """A colon introducing a list in the summary: the top third should be sentences, not a catalogue."""
    rx = re.compile(r":\s+[^.]{0,80},")
    return [_f("T39-summary-catalogue", "warn", u, "Summary sentence turns into a colon-introduced list",
               "Say what the items let you do, in one plain clause; leave the list to Skills.")
            for u, t in _prose(r) if u.kind in ("summary", "label") and rx.search(t)]


# Value-proposition slogans: an identity defined by the benefit it delivers ("who makes X reliable enough to…").
SLOGAN = (r"\b(who|that|which) (makes?|helps?|turns?|enables?|empowers?|brings?|gives?|lets?)\b[^.]{0,80}"
          r"\b(enough|depend on|rely on|trust|confidence|matters?|possible|real)\b"
          r"|\bthat proves? it\b|\b(and|then) proves? it\b")


@rule("universal")
def rule_slogan(r: Resume):
    rx = re.compile(SLOGAN, re.I)
    return [_f("T40-slogan", "warn", u, f"Value-proposition slogan: '{rx.search(t).group(0)[:60]}'",
               "State what you do and where, plainly; let the reader draw the benefit.")
            for u, t in _prose(r) if rx.search(t)]


RULES = [v for k, v in sorted(globals().items()) if k.startswith("rule_")]
