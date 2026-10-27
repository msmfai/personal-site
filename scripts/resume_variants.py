"""Resume versions as overlays on the master resume (_data/content.yml).

A version file never copies facts. It selects, orders, and reframes what the master
already says. The only new prose a version may carry is `label` and `summary`, and those
must be grounded in the master or the brand studio's source.

Version files live OUTSIDE this public repo (in the private brand studio), and rendered
versions go to build/ (gitignored), never to assets/ (deployed).

Schema (all keys optional):
  compose:       [fragment.yml, ...]      # paths relative to the version file; merged first, in order
                                          # (bullet_replace merges by prefix, bullet_add and lint_ignore accumulate)
  target:        free text                # who this version is for (not rendered)
  lint_facets:   [facet, ...]             # linter composition for this version
  label:         text                     # replaces cv.label
  location:      text                     # replaces cv.location (header); "" hides it
  summary:       text                     # replaces cv.summary
  sections_order: [Experience, ...]       # sections to render, in order; others are dropped
  entry_order:   {Experience: [prefix, ...]}   # reorder entries by company/institution prefix
  entry_drop:    {Experience: [name, ...]}    # remove whole entries (exact company/institution name)
  entry_dates:   {Experience: {prefix: {start_date: "2023"}}}  # restate an entry's dates (must be in the source)
  drop:          [bullet prefix, ...]     # remove bullets; each prefix must match exactly one bullet
  lead:          [bullet prefix, ...]     # move bullets to the top of their entry
  publications_order: [title prefix, ...] # listed first, in this order; the rest keep master order
  publications_drop:  [title prefix, ...]
  skills_keep:   {group label: [keyword, ...]}  # keep only these groups/keywords (must exist in master)
  bullet_replace: [{prefix, text, source: [IDs]}]  # reword one bullet; must cite the studio source IDs behind it
  bullet_add:    [{entry, text, source: [IDs]}]  # add a bullet to an entry (exact name); must cite source IDs
  entry_summary: {Experience: {name: {text, source: [IDs]}}}  # reword an entry's subheading; must cite source IDs
  entry_area:    {Education: {studyType or name: {text, source: [IDs]}}}  # reword an entry's field line; must cite source IDs
  lint_ignore:   [{rule, path, why}]          # deliberate exceptions the linter can't know about; each needs a reason
  skills_set:    [{label, keywords, source: [IDs]}]  # a version's own skills block; must cite source IDs
  interests_keep: [group name, ...]
"""
from __future__ import annotations

import copy
from pathlib import Path

import yaml

LIST_MERGE = {"compose", "drop", "lead", "lint_facets", "publications_drop"}


class VariantError(ValueError):
    pass


def load_spec(path: Path, _seen=None) -> dict:
    path = Path(path).resolve()
    _seen = _seen or set()
    if path in _seen:
        raise VariantError(f"compose cycle at {path}")
    _seen.add(path)
    spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    merged: dict = {}
    for frag in spec.get("compose", []) or []:
        _merge(merged, load_spec(path.parent / frag, _seen))
    _merge(merged, {k: v for k, v in spec.items() if k != "compose"})
    merged["_file"] = str(path)
    return merged


# Keyed lists: a later spec's entry replaces an earlier one with the same key, others accumulate.
# This lets a role-specific spec reword one bullet without restating every bullet its base rewords.
KEYED_MERGE = {"bullet_replace": lambda r: r.get("prefix"),
               "bullet_add": lambda r: (r.get("entry"), r.get("text")),
               "lint_ignore": lambda r: (r.get("rule"), r.get("path"))}


def _merge(base: dict, over: dict) -> None:
    for k, v in over.items():
        if v is None and (k in LIST_MERGE or k in KEYED_MERGE):  # an empty `drop:` must not erase a base's list
            continue
        if k in KEYED_MERGE and isinstance(v, list):
            key = KEYED_MERGE[k]
            merged = {key(r): r for r in (base.get(k) or [])}
            for r in v:
                merged[key(r)] = r
            base[k] = list(merged.values())
        elif k in LIST_MERGE and isinstance(v, list):
            base[k] = list(dict.fromkeys((base.get(k) or []) + v))
        elif isinstance(v, dict) and isinstance(base.get(k), dict):
            base[k] = {**base[k], **v}
        else:
            base[k] = v


def _match_one(items: list[str], prefix: str, where: str) -> int:
    hits = [i for i, t in enumerate(items) if str(t).lstrip('"').startswith(prefix)]
    if len(hits) != 1:
        raise VariantError(f"{where}: prefix {prefix!r} matched {len(hits)} items (need exactly 1)")
    return hits[0]


def apply(content: dict, spec: dict) -> dict:
    out = copy.deepcopy(content)
    cv = out["cv"]
    sections = cv.get("sections", {}) or {}

    if "label" in spec:
        cv["label"] = spec["label"]
    if "location" in spec:
        cv["location"] = spec["location"] or ""
    if "summary" in spec:
        cv["summary"] = spec["summary"].strip()
    if spec.get("lint_facets"):
        cv["lint_facets"] = spec["lint_facets"]

    # bullets: drop and lead, across Experience and Education
    all_bullets = [(sec, e) for sec in ("Experience", "Education") for e in sections.get(sec, []) or []]
    for prefix in spec.get("drop", []) or []:
        owners = [e for _, e in all_bullets if any(str(h).startswith(prefix) for h in e.get("highlights") or [])]
        if len(owners) != 1:
            raise VariantError(f"drop: prefix {prefix!r} matched bullets in {len(owners)} entries (need exactly 1)")
        hl = owners[0]["highlights"]
        hl.pop(_match_one(hl, prefix, "drop"))
    for prefix in reversed(spec.get("lead", []) or []):
        owners = [e for _, e in all_bullets if any(str(h).startswith(prefix) for h in e.get("highlights") or [])]
        if len(owners) != 1:
            raise VariantError(f"lead: prefix {prefix!r} matched bullets in {len(owners)} entries (need exactly 1)")
        hl = owners[0]["highlights"]
        hl.insert(0, hl.pop(_match_one(hl, prefix, "lead")))

    # bullet replace (reworded from the source; every replacement cites its IDs)
    dropped = set(spec.get("drop", []) or [])
    for r in spec.get("bullet_replace", []) or []:
        if r.get("prefix") in dropped:  # a role dropped a bullet its base rewords
            continue
        if not r.get("source"):
            raise VariantError(f"bullet_replace {r.get('prefix')!r}: needs source IDs")
        owners = [e for _, e in all_bullets if any(str(h).startswith(r["prefix"]) for h in e.get("highlights") or [])]
        if len(owners) != 1:
            raise VariantError(f"bullet_replace: prefix {r['prefix']!r} matched bullets in {len(owners)} entries (need exactly 1)")
        hl = owners[0]["highlights"]
        hl[_match_one(hl, r["prefix"], "bullet_replace")] = r["text"].strip()

    # entry summary (subheading) rewording
    for sec, by_name in (spec.get("entry_summary") or {}).items():
        entries = sections.get(sec, []) or []
        names = [e.get("company") or e.get("institution") or "" for e in entries]
        for n, r in by_name.items():
            if not r.get("source"):
                raise VariantError(f"entry_summary.{sec}.{n}: needs source IDs")
            if names.count(n) != 1:
                raise VariantError(f"entry_summary.{sec}: {n!r} matched {names.count(n)} entries (need exactly 1)")
            entries[names.index(n)]["summary"] = r["text"].strip()
    # entry area (an Education entry's field line), keyed by studyType prefix or exact name,
    # since both Liverpool degrees share an institution name
    for sec, by_key in (spec.get("entry_area") or {}).items():
        entries = sections.get(sec, []) or []
        for key, r in by_key.items():
            if not r.get("source"):
                raise VariantError(f"entry_area.{sec}.{key}: needs source IDs")
            hits = [e for e in entries
                    if str(e.get("studyType", "")).startswith(key) or (e.get("company") or e.get("institution")) == key]
            if len(hits) != 1:
                raise VariantError(f"entry_area.{sec}: {key!r} matched {len(hits)} entries (need exactly 1)")
            hits[0]["area"] = r["text"].strip()
    if spec.get("lint_ignore"):
        for x in spec["lint_ignore"]:
            if not (x.get("rule") and x.get("why")):
                raise VariantError("lint_ignore: each entry needs a rule and a why")
        cv["lint_ignore"] = spec["lint_ignore"]

    # bullet add (from the source; every addition cites its IDs)
    for r in spec.get("bullet_add", []) or []:
        if not r.get("source"):
            raise VariantError(f"bullet_add to {r.get('entry')!r}: needs source IDs")
        hits = [e for _, e in all_bullets if (e.get("company") or e.get("institution")) == r["entry"]]
        if len(hits) != 1:
            raise VariantError(f"bullet_add: entry {r['entry']!r} matched {len(hits)} entries (need exactly 1)")
        hits[0].setdefault("highlights", []).append(r["text"].strip())

    # entry order
    for sec, prefixes in (spec.get("entry_order") or {}).items():
        entries = sections.get(sec, []) or []
        names = [e.get("company") or e.get("institution") or "" for e in entries]
        picked = [_match_one(names, p, f"entry_order.{sec}") for p in prefixes]
        rest = [i for i in range(len(entries)) if i not in picked]
        sections[sec] = [entries[i] for i in picked + rest]

    # entry drop (exact names, so "Electronic Arts" can't also catch "Electronic Arts (SEED)")
    for sec, names_to_drop in (spec.get("entry_drop") or {}).items():
        entries = sections.get(sec, []) or []
        names = [e.get("company") or e.get("institution") or "" for e in entries]
        for n in names_to_drop:
            if names.count(n) != 1:
                raise VariantError(f"entry_drop.{sec}: {n!r} matched {names.count(n)} entries (need exactly 1)")
        sections[sec] = [e for e, nm in zip(entries, names) if nm not in names_to_drop]

    # entry dates
    for sec, by_prefix in (spec.get("entry_dates") or {}).items():
        entries = sections.get(sec, []) or []
        names = [e.get("company") or e.get("institution") or "" for e in entries]
        for prefix, dates in by_prefix.items():
            entry = entries[_match_one(names, prefix, f"entry_dates.{sec}")]
            unknown = set(dates) - {"start_date", "end_date"}
            if unknown:
                raise VariantError(f"entry_dates.{sec}.{prefix}: unknown keys {sorted(unknown)}")
            entry.update({k: str(v) for k, v in dates.items()})

    # publications
    pubs = sections.get("Publications", []) or []
    titles = [p.get("title", "") for p in pubs]
    dropped = {_match_one(titles, p, "publications_drop") for p in spec.get("publications_drop", []) or []}
    firsts = [_match_one(titles, p, "publications_order") for p in spec.get("publications_order", []) or []]
    order = [i for i in firsts if i not in dropped] + [i for i in range(len(pubs)) if i not in firsts and i not in dropped]
    if pubs:
        sections["Publications"] = [pubs[i] for i in order]

    # skills
    if "skills_keep" in spec:
        groups = {g.get("label"): g for g in sections.get("Skills", []) or []}
        kept = []
        for label, kws in spec["skills_keep"].items():
            if label not in groups:
                raise VariantError(f"skills_keep: no Skills group {label!r}")
            missing = [k for k in kws if k not in groups[label].get("keywords", [])]
            if missing:
                raise VariantError(f"skills_keep.{label}: not in master: {missing}")
            kept.append({**groups[label], "keywords": list(kws)})
        sections["Skills"] = kept
    if "skills_set" in spec:
        for g in spec["skills_set"]:
            if not g.get("source"):
                raise VariantError(f"skills_set {g.get('label')!r}: needs source IDs")
        sections["Skills"] = [{"label": g["label"], "keywords": list(g["keywords"])} for g in spec["skills_set"]]
    if "interests_keep" in spec:
        groups = {g.get("name"): g for g in sections.get("Interests", []) or []}
        unknown = [n for n in spec["interests_keep"] if n not in groups]
        if unknown:
            raise VariantError(f"interests_keep: unknown groups {unknown}")
        sections["Interests"] = [groups[n] for n in spec["interests_keep"]]

    # section order (last, so dropped sections vanish)
    if spec.get("sections_order"):
        unknown = [s for s in spec["sections_order"] if s not in sections]
        if unknown:
            raise VariantError(f"sections_order: unknown sections {unknown}")
        cv["sections"] = {s: sections[s] for s in spec["sections_order"]}
    else:
        cv["sections"] = sections
    return out


def variant_name(spec: dict) -> str:
    return Path(spec["_file"]).stem
