"""Lint the resume source.

  python -m scripts.resume_lint                                   # default preset (ai-lab-scientist)
  python -m scripts.resume_lint --preset graphics-re              # a named composition
  python -m scripts.resume_lint --role research-engineer --specialism graphics --audience frontier-lab
  python -m scripts.resume_lint --preset consulting --specialism materials-science   # preset plus extra facets
  python -m scripts.resume_lint --no-llm                          # code rules only (no API call)
  python -m scripts.resume_lint --list-rules                      # facet axes, presets, and which rules each facet turns on
  python -m scripts.resume_lint --jd postings/deepmind-rs.txt    # add job-description coverage
  python -m scripts.resume_lint --variant ~/studio/projections/resume-versions/x.yml   # lint one version
  python -m scripts.resume_lint --variant V.yml --readers R.yml   # judge against the named decision-makers (reader panel)
  python -m scripts.resume_lint --json                            # machine-readable
  python -m scripts.resume_lint --min warn                        # hide info-level findings

The resume file may carry its own composition: `cv.lint_facets: [research-engineer, graphics, frontier-lab]`
or `cv.lint_preset: quant`. Command-line facets are added on top.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import readers, rules_ai_tells, rules_audience, rules_jd, rules_llm, rules_role, rules_slop, rules_structure, rules_text
from .facets import AXES, DEFAULT_PRESET, PRESETS, describe, is_active, resolve, select
from .model import SEVERITIES, load
from .report import as_json, as_text

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FILE = ROOT / "_data" / "content.yml"
CODE_RULES = rules_text.RULES + rules_slop.RULES + rules_ai_tells.RULES + rules_structure.RULES + rules_role.RULES + rules_audience.RULES


def list_rules(active: set[str]) -> str:
    out = []
    for axis, vals in AXES.items():
        out.append(f"[{axis}]")
        for v, desc in vals.items():
            mark = "*" if v in active else " "
            code = [r.__name__.removeprefix("rule_") for r in CODE_RULES if v in _needs_flat(r)]
            llm = [rid for rid, needs, _ in rules_llm.JUDGE_RULES if v in _needs_flat_t(needs)]
            out.append(f" {mark} {v:18} {desc}")
            out.append(f"   {'':18}   code: {', '.join(code) or '-'}")
            out.append(f"   {'':18}   llm:  {', '.join(llm) or '-'}")
    always_llm = [rid for rid, needs, _ in rules_llm.JUDGE_RULES if not needs]
    out.append(f"\nalways-on llm: {', '.join(always_llm)}")
    out.append("\npresets:")
    for name, facets in PRESETS.items():
        out.append(f"  {name:18} = {' + '.join(sorted(facets)) if name != 'all' else 'every facet'}")
    out.append(f"\nactive: {describe(active)}   (* above)")
    return "\n".join(out)


def _needs_flat(r):
    return _needs_flat_t(getattr(r, "needs", ()))


def _needs_flat_t(needs):
    return {n for need in needs for n in (need if isinstance(need, list) else [need])}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("file", nargs="?", default=DEFAULT_FILE, type=Path)
    p.add_argument("--preset", choices=list(PRESETS), help=f"named facet composition (default: the file's lint_preset, else {DEFAULT_PRESET})")
    p.add_argument("--role", choices=list(AXES["role"]))
    p.add_argument("--specialism", action="append", default=[], choices=list(AXES["specialism"]), help="repeatable")
    p.add_argument("--audience", choices=list(AXES["audience"]))
    p.add_argument("--facet", action="append", default=[], help="any facet value, repeatable (e.g. --facet graphics)")
    p.add_argument("--variant", type=Path, help="resume version spec; lints the master with that overlay applied, against the version's own facets and PDF")
    p.add_argument("--jd", type=Path, help="job description text file; adds JD coverage rules (J01-J04)")
    p.add_argument("--readers", type=Path, help="reader panel YAML (decision-makers); adds per-reader checks and one judge read per reader")
    p.add_argument("--reader", action="append", default=[], help="limit the panel to these reader ids (repeatable)")
    p.add_argument("--list-rules", action="store_true")
    p.add_argument("--no-llm", action="store_true", help="skip the LLM-judged rules")
    p.add_argument("--llm-only", action="store_true", help="skip the code rules")
    p.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    p.add_argument("--json", action="store_true")
    p.add_argument("--min", default="info", choices=SEVERITIES, help="lowest severity to show")
    p.add_argument("--rules", default="", help="comma-separated rule id prefixes to include")
    p.add_argument("--no-color", action="store_true")
    p.add_argument("--fail-on", default="error", choices=SEVERITIES + ("never",))
    args = p.parse_args(argv)

    if args.variant:
        import yaml
        sys.path.insert(0, str(ROOT / "scripts"))
        from resume_variants import VariantError, apply, load_spec, variant_name
        try:
            spec = load_spec(args.variant)
            merged = apply(yaml.safe_load(args.file.read_text(encoding="utf-8")), spec)
        except VariantError as e:
            print(f"ERROR in {args.variant}: {e}")
            return 1
        vdir = ROOT / "build" / "resume" / "variants"
        vdir.mkdir(parents=True, exist_ok=True)
        name = variant_name(spec)
        merged_file = vdir / f"{name}.content.yml"
        dumped = yaml.safe_dump(merged, sort_keys=False, allow_unicode=True, width=10_000)
        if not merged_file.exists() or merged_file.read_text(encoding="utf-8") != dumped:
            merged_file.write_text(dumped, encoding="utf-8")  # rewrite only on change, so a fresh PDF isn't marked stale
        resume = load(merged_file, pdf=vdir / f"{name}.pdf")
        args.file = merged_file
    else:
        resume = load(args.file)
    file_facets = resume.cv.get("lint_facets") or []
    explicit = [x for x in (args.role, args.audience) if x] + args.specialism + args.facet + list(file_facets)
    preset = args.preset or resume.cv.get("lint_preset") or (None if explicit else DEFAULT_PRESET)
    active = resolve(preset, explicit)

    if args.list_rules:
        print(list_rules(active))
        return 0

    findings, notes, llm_report = [], [f"composition: {describe(active)}" + (f"  (preset {preset})" if preset else "")], None
    if not args.llm_only:
        for rule in select(CODE_RULES, active):
            findings.extend(rule(resume))
        if args.jd:
            findings.extend(rules_jd.run(resume, args.jd))
    panel = readers.load_panel(args.readers) if args.readers else None
    if panel:
        notes.append(f"panel: {panel.get('route', args.readers)}")
        if not args.llm_only:
            findings.extend(readers.run(resume, panel, set(args.reader) or None))
    if not args.no_llm:
        if panel:  # one read per decision-maker, in their chair, instead of the generic persona
            panel_reports = []
            for rd in panel["readers"]:
                if args.reader and rd["id"] not in args.reader:
                    continue
                f_, rep, note = rules_llm.run(resume, active, effort=args.effort, who=rd["persona"].strip(),
                                              extra=readers.judge_rules(rd), tag=f"{rd['id']}:")
                findings.extend(f_)
                notes.append(f"{rd['id']}: {note}")
                if rep:
                    panel_reports.append((rd, rep))
            llm_report = None
            for rd, rep in panel_reports:
                notes.append(f"{rd['name']} — most flattering: {rep.most_flattering_read}")
                notes.append(f"{rd['name']} — least flattering: {rep.least_flattering_read}")
                for i, t in enumerate(rep.top_issues, 1):
                    notes.append(f"{rd['name']} — issue {i}: {t}")
        else:
            llm_findings, llm_report, note = rules_llm.run(resume, active, effort=args.effort)
            findings.extend(llm_findings)
            notes.append(note)

    if panel and panel.get("max_pages"):  # the panel's route sets the page target (P01), not the generic two-page rule
        findings = [f for f in findings if f.rule != "S14-pdf-pages"]
    ignores = resume.cv.get("lint_ignore") or []  # deliberate exceptions recorded in the version, each with a reason
    if ignores:
        def _ignored(f):
            return next((x for x in ignores if f.rule.startswith(x["rule"]) and (not x.get("path") or f.path.startswith(x["path"]))), None)
        for f in findings:
            x = _ignored(f)
            if x:
                notes.append(f"accepted {f.rule} at {f.path}: {x['why']}")
        findings = [f for f in findings if not _ignored(f)]
    keep = SEVERITIES[: SEVERITIES.index(args.min) + 1]
    findings = [f for f in findings if f.severity in keep]
    if args.rules:
        prefixes = [s.strip() for s in args.rules.split(",") if s.strip()]
        findings = [f for f in findings if any(f.rule.startswith(x) for x in prefixes)]

    rel = str(args.file.relative_to(ROOT)) if args.file.is_relative_to(ROOT) else str(args.file)
    print(as_json(findings, llm_report, notes) if args.json else as_text(findings, rel, not args.no_color, notes, llm_report))

    if args.fail_on != "never":
        bad = SEVERITIES[: SEVERITIES.index(args.fail_on) + 1]
        return 1 if any(f.severity in bad for f in findings) else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
