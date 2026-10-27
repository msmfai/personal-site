# marinmoran.xyz: satellite of the Personal Brand Studio

This repo lives inside the studio (`../`) and is edited from there. It stays its own git
repo (remote `msmfai/personal-site`, deployed by its GitHub Action), but it is **not** the
source of truth for any fact about Marin.

- Facts originate in `../main/source/` (read `../main/CLAUDE.md`). This site is a
  projection of them: `_data/content.yml`, `_data/timeline.yml`, `_bibliography/papers.bib`,
  `_pages/*`, and the résumé built by `scripts/build_resume.py`.
- To change a fact: change it in `../main/source/` first (renormalize, lint `ok`), then
  update the site to match. Never put a fact here that isn't in the source.
- Never name early clients, and nothing from `../main/private/`.
- Commit here (in this repo) only when Marin asks; never commit it from the studio.

@AGENTS.md
