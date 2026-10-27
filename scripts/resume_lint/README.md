# resume_lint

Linters over `_data/content.yml` (the resume source). Every finding points at a
line in that file, names a rule, and says what to do.

```
pip install -r scripts/resume_lint/requirements.txt
python -m scripts.resume_lint --list-rules                 # the facet axes, presets, and what each facet turns on
python -m scripts.resume_lint --no-llm                     # code rules only, instant, free
python -m scripts.resume_lint --preset graphics-re         # a named composition
python -m scripts.resume_lint --role research-engineer --specialism graphics --audience frontier-lab
python -m scripts.resume_lint --preset consulting --specialism materials-science   # preset plus extras
python -m scripts.resume_lint                              # adds the LLM judge (needs ANTHROPIC_API_KEY or `ant auth login`)
python -m scripts.resume_lint --min warn                   # hide info-level
python -m scripts.resume_lint --json > out.json
python -m scripts.resume_lint variants/quant.yml           # lint a different resume file
```

Exit code is 1 when there is an `error`-level finding (`--fail-on warn|info|never`).

## Composition

A resume version is a **set of facet values** drawn from orthogonal axes.
Rules declare what they need and fire when it's present. Nothing inherits.

```
base        universal, technical                 always on
role        ai-scientist | research-engineer | engineer
specialism  graphics, materials-science, ml-evaluation, hpc-systems      (zero or more)
audience    frontier-lab | big-tech | academia | buyer | investor | trading-firm
```

- **role** is what the reader reads you *as*. A scientist is read for findings and
  first-author work; a research engineer for the systems that made the research
  run and the bridge to shipping; an engineer for ownership, production, scope.
- **specialism** is pedigree: the ultra-specialist signals a reader from that field
  looks for (the right venue, the right vocabulary, a scale number).
- **audience** is who's holding the page, and sets the persona the LLM judge adopts.
  The persona is composed too: "a research lead at a frontier lab, hiring for a
  research engineer role, who knows the graphics field well".

A rule can need one value, all of several (`@rule("ml-evaluation", "ai-scientist")`),
or any of several (`@rule(["big-tech", "frontier-lab"])`).

**Presets** are sugar for common sets and can be extended on the command line:

```
ai-lab-scientist   = ai-scientist + frontier-lab                   (default)
ai-lab-re          = research-engineer + hpc-systems + frontier-lab
graphics-re        = research-engineer + graphics + big-tech
graphics-scientist = ai-scientist + graphics + big-tech
engineer           = engineer + big-tech
academic           = ai-scientist + academia
consulting         = ai-scientist + ml-evaluation + buyer
quant              = research-engineer + trading-firm
founder            = engineer + investor
```

A resume file can carry its own composition, so each domain-specific version
lints itself: `cv.lint_facets: [research-engineer, graphics, frontier-lab]` or
`cv.lint_preset: quant`. Command-line facets are added on top.

Axes, presets, and personas live in `facets.py`. Adding a facet value is one
line there plus whichever rules you tag with it.

## Principles (from a survey of open-source tailoring pipelines, 2026)

Hard lints are deterministic and free; soft lints are the LLM judge. Both follow the
points every serious pipeline converged on:

1. **Source is truth; versions are views.** Emphasis may change per reader, claims may not.
2. **No invented facts.** Every number in a judge rewrite must already exist in the source
   (`G01-ungrounded`, error). JD rules suggest adding only terms the body can support.
3. **Shown beats listed.** A skill demonstrated in a bullet outweighs one in the Skills list
   (`S16`, `J03`, and every ATS scorer surveyed).
4. **Metrics need context.** A percentage without a baseline reads as inflated (`T26`).
5. **Read as a person wrote it.** Em dashes, stock "power verbs", symmetrical bullets, and
   template residue are now screened for as AI tells (`T23`-`T27`, `L15`, `L16`).
6. **Fit the page budget at the source.** Estimated rendered lines with a cut order (`S18`).
7. **Scores model the screen; they aren't the screen.** JD coverage is uncalibrated and labelled so.
8. **Range is not scatter.** Breadth across fields is never reported as a defect. What's checked
   is that each research item is visibly originated by the candidate (`R-OW01`, `L-OW01`) and
   that the summary names the thread connecting them (`R-OW02`, `L-OW02`). The judge prompt
   forbids recommending a narrower focus.

## Rule families

| Prefix | File | What |
|---|---|---|
| `T01`–`T22` | `rules_text.py` | Per-bullet text rules (base) |
| `T23`–`T27`, `S18`, `R-OW` | `rules_slop.py` | AI-slop tells, metric context, line budget, ownership and thread |
| `J01`–`J04` | `rules_jd.py` | Job-description coverage, only with `--jd FILE` |
| `G01` | `rules_llm.py` | Grounding check on judge rewrites |
| `S01`–`S17` | `rules_structure.py` | Whole-document structure and PDF rules (base, a few role/audience-gated) |
| `R-SC`, `R-RE`, `R-EN` | `rules_role.py` | Role rules |
| `P-GR`, `P-MS`, `P-EV`, `P-HPC` | `rules_role.py` | Specialism (pedigree) rules |
| `D-AI`, `D-CO`, `D-QU`, `D-FO` | `rules_audience.py` | Audience rules |
| `L01`–`L14`, `L-SC`, `L-RE`, `L-EN`, `L-GR`, `L-MS`, `L-EV`, `L-HPC`, `L-AI`, `L-CO`, `L-QU`, `L-FO` | `rules_llm.py` | LLM-judged rules, same facet gating; only active rules are sent. Also returns a whole-document read: top issues plus the most and least flattering honest impression from that reader's chair |

Add a code rule: `@rule(<needs>) def rule_*(resume) -> list[Finding]` in the
right file; it's picked up automatically. Add a judge rule: one tuple in
`JUDGE_RULES` with its needs.

Model is `claude-opus-5` by default (`RESUME_LINT_MODEL` to change). One call
per run over the whole resume, roughly a few cents.
