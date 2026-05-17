#!/usr/bin/env python3
"""
Build a PDF and DOCX resume from _data/content.yml using Pandoc.

Run:  python scripts/build_resume.py            # auto-tune to fit 2 pages
      python scripts/build_resume.py --preset compact     # force a preset
      python scripts/build_resume.py --target-pages 1     # auto-tune to 1 page
      python scripts/build_resume.py --no-auto            # use the default preset, do not auto-tune
      python scripts/build_resume.py --list-presets       # print the ladder

Outputs: assets/resume/resume.pdf
         assets/resume/resume.docx

Requires:
  * Python 3.9+, PyYAML, pypdf       (pip install pyyaml pypdf)
  * Pandoc                            (https://pandoc.org)
  * A LaTeX engine                    (xelatex from TeX Live or MiKTeX)

pypdf is needed for the auto-tune loop: Pandoc emits PDF 1.5 with
compressed object streams, so plain byte-counting cannot read the page
count. If you only need a one-shot build at a fixed preset, --no-auto or
--preset NAME both skip the page-count step.

Styling follows the conventions favoured by Jane Street and similar quant
firms: serif, single-column, ~10–11pt, narrow-ish margins, no colour,
right-aligned dates, reverse chronological, tight section spacing.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTENT_FILE = ROOT / "_data" / "content.yml"
OUT_DIR = ROOT / "assets" / "resume"
BUILD_DIR = ROOT / "build" / "resume"

PDF_ENGINE = os.environ.get("RESUME_PDF_ENGINE", "xelatex")


# -----------------------------------------------------------------------------
# Compactness ladder, ordered from loosest to tightest.
# Auto-tune picks the loosest preset whose PDF still fits the target page count.
# Tweak the numbers below to taste; adding new presets is fine.
# -----------------------------------------------------------------------------
PRESETS: list[dict] = [
    dict(name="loose",       fontsize=11.0, margin=1.00, parskip=6, sec_top=12, sec_bot=6, linespread=1.00, itemsep=4),
    dict(name="comfortable", fontsize=11.0, margin=0.85, parskip=5, sec_top=10, sec_bot=5, linespread=1.00, itemsep=3),
    dict(name="default",     fontsize=11.0, margin=0.75, parskip=4, sec_top=10, sec_bot=4, linespread=1.00, itemsep=2),
    dict(name="compact",     fontsize=11.0, margin=0.65, parskip=3, sec_top=8,  sec_bot=3, linespread=1.00, itemsep=2),
    dict(name="tighter",     fontsize=10.5, margin=0.65, parskip=3, sec_top=8,  sec_bot=3, linespread=0.98, itemsep=2),
    dict(name="very_tight",  fontsize=10.5, margin=0.55, parskip=3, sec_top=7,  sec_bot=3, linespread=0.97, itemsep=1),
    dict(name="ultra_tight", fontsize=10.0, margin=0.55, parskip=2, sec_top=6,  sec_bot=2, linespread=0.96, itemsep=1),
    dict(name="squeeze",     fontsize=10.0, margin=0.50, parskip=2, sec_top=6,  sec_bot=2, linespread=0.95, itemsep=1),
    dict(name="max",         fontsize=10.0, margin=0.40, parskip=1, sec_top=5,  sec_bot=2, linespread=0.92, itemsep=0),
]

DEFAULT_PRESET_NAME = "default"
DEFAULT_TARGET_PAGES = 2


# =============================================================================
# Helpers
# =============================================================================

def tex_escape(s) -> str:
    """Escape LaTeX special characters for strings interpolated into raw-LaTeX
    blocks. Markdown-rendered prose is escaped by Pandoc; we only need this
    where we emit \\textbf{...} and the like directly."""
    if not isinstance(s, str):
        return s
    table = [
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ]
    out = s
    for old, new in table:
        out = out.replace(old, new)
    return out


def format_month_year(value) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, str) and value.strip().lower() == "present":
        return "Present"
    if hasattr(value, "strftime"):
        return value.strftime("%b %Y")
    s = str(value).strip()
    parts = s.split("-")
    try:
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        return date(year, month, 1).strftime("%b %Y")
    except (ValueError, IndexError):
        return s


def date_range(start, end) -> str:
    a, b = format_month_year(start), format_month_year(end)
    if not a and not b:
        return ""
    if a == b:
        return a
    return f"{a} – {b}"


def social_url(network: str, username: str) -> str:
    table = {
        "LinkedIn": f"https://linkedin.com/in/{username}",
        "GitHub": f"https://github.com/{username}",
        "Twitter": f"https://twitter.com/{username}",
        "X": f"https://x.com/{username}",
        "ORCID": f"https://orcid.org/{username}",
        "Scholar": f"https://scholar.google.com/citations?user={username}",
    }
    return table.get(network, f"https://{network.lower()}.com/{username}")


def count_pdf_pages(pdf_path: Path) -> int:
    """Return the page count of a PDF. Tries pypdf, then PyPDF2. Falls back
    to a regex on raw PDF bytes, which only works for *uncompressed* PDFs
    (Pandoc + xelatex emits PDF 1.5 with compressed object streams, so the
    fallback returns 0 there — install pypdf for auto-tune to work)."""
    try:
        from pypdf import PdfReader  # type: ignore
        return len(PdfReader(str(pdf_path)).pages)
    except ImportError:
        pass
    try:
        from PyPDF2 import PdfReader  # type: ignore
        return len(PdfReader(str(pdf_path)).pages)
    except ImportError:
        pass
    data = pdf_path.read_bytes()
    n = len(re.findall(rb"/Type\s*/Page\b", data))
    if n == 0:
        print(
            "WARN: page count returned 0. Install pypdf for accurate counts:\n"
            "      pip install pypdf",
            file=sys.stderr,
        )
    return n


def require(cmd: str) -> None:
    if shutil.which(cmd) is None:
        sys.exit(f"ERROR: '{cmd}' not found on PATH. Install it before running.")


# =============================================================================
# Markdown rendering (uses preset values in the LaTeX preamble)
# =============================================================================

def render_markdown(content: dict, preset: dict) -> str:
    cv = content["cv"]
    lines: list[str] = []

    lines += [
        "---",
        "documentclass: article",
        f"fontsize: {preset['fontsize']}pt",
        'mainfont: "Times New Roman"',
        f"geometry: \"margin={preset['margin']}in\"",
        "colorlinks: false",
        "linkcolor: black",
        "urlcolor: black",
        "header-includes: |",
        "  \\pagestyle{empty}",
        f"  \\setlength{{\\parskip}}{{{preset['parskip']}pt}}",
        "  \\setlength{\\parindent}{0pt}",
        f"  \\linespread{{{preset['linespread']}}}",
        "  \\usepackage{titlesec}",
        f"  \\titlespacing*{{\\section}}{{0pt}}{{{preset['sec_top']}pt}}{{{preset['sec_bot']}pt}}",
        "  \\titleformat{\\section}{\\large\\bfseries\\MakeUppercase}{}{0em}{}",
        "  \\usepackage{enumitem}",
        f"  \\setlist[itemize]{{topsep=0pt,partopsep=0pt,parsep=0pt,"
        f"itemsep={preset['itemsep']}pt,leftmargin=*}}",
        "---",
        "",
    ]

    # ---- Header (name + contact) ----
    name = cv.get("name", "")
    label = cv.get("label", "")
    location = cv.get("location", "")
    socials = cv.get("social_networks", []) or []

    lines.append("\\begin{center}")
    lines.append(f"  {{\\LARGE \\textbf{{{tex_escape(name)}}}}} \\\\")
    if label:
        lines.append(f"  \\vspace{{2pt}} {tex_escape(label)} \\\\")
    contact_bits: list[str] = []
    if location:
        contact_bits.append(tex_escape(location))
    for s in socials:
        net, user = s.get("network", ""), s.get("username", "")
        if net and user:
            url = social_url(net, user)
            contact_bits.append(
                f"\\href{{{url}}}{{{tex_escape(net)}: {tex_escape(user)}}}"
            )
    if contact_bits:
        lines.append(
            "  \\vspace{2pt} \\small "
            + " \\; $\\cdot$ \\; ".join(contact_bits)
        )
    lines.append("\\end{center}")
    lines.append("")

    # ---- Summary ----
    summary = (cv.get("summary") or "").strip()
    if summary:
        lines.append("# Summary")
        lines.append("")
        lines.append(summary)
        lines.append("")

    sections = cv.get("sections", {}) or {}

    # ---- Experience ----
    if "Experience" in sections:
        lines.append("# Experience")
        lines.append("")
        for entry in sections["Experience"]:
            company = entry.get("company", "")
            position = entry.get("position", "")
            loc = entry.get("location", "")
            dates = date_range(entry.get("start_date"), entry.get("end_date"))
            summary_line = (entry.get("summary") or "").strip()

            lines.append(
                f"\\textbf{{{tex_escape(company)}}}, *{position}* "
                f"\\hfill {dates} \\\n"
            )
            if loc:
                lines.append(f"\\textit{{\\small {tex_escape(loc)}}}\\")
                lines.append("")
            if summary_line:
                lines.append(f"*{summary_line}*")
                lines.append("")
            for h in entry.get("highlights", []) or []:
                lines.append(f"- {h}")
            lines.append("")

    # ---- Education ----
    if "Education" in sections:
        lines.append("# Education")
        lines.append("")
        for entry in sections["Education"]:
            institution = entry.get("institution", "")
            area = entry.get("area", "")
            study_type = entry.get("studyType", "")
            loc = entry.get("location", "")
            dates = date_range(entry.get("start_date"), entry.get("end_date"))

            descriptor = ", ".join(p for p in [study_type, area] if p)

            lines.append(
                f"\\textbf{{{tex_escape(institution)}}}, *{descriptor}* "
                f"\\hfill {dates} \\\n"
            )
            if loc:
                lines.append(f"\\textit{{\\small {tex_escape(loc)}}}\\")
                lines.append("")
            for h in entry.get("highlights", []) or []:
                lines.append(f"- {h}")
            lines.append("")

    # ---- Skills ----
    if "Skills" in sections:
        lines.append("# Skills")
        lines.append("")
        for group in sections["Skills"]:
            label_g = group.get("label", "")
            keywords = group.get("keywords", []) or []
            if not keywords:
                continue
            lines.append(f"**{label_g}.** {', '.join(keywords)}")
            lines.append("")

    # ---- Interests ----
    if "Interests" in sections:
        lines.append("# Interests")
        lines.append("")
        for group in sections["Interests"]:
            name_g = group.get("name", "")
            keywords = group.get("keywords", []) or []
            if not keywords:
                continue
            lines.append(f"**{name_g}.** {', '.join(keywords)}")
            lines.append("")

    return "\n".join(lines)


# =============================================================================
# Pandoc invocation
# =============================================================================

def build_pdf(md_path: Path, pdf_path: Path) -> None:
    subprocess.run(
        [
            "pandoc",
            str(md_path),
            "-o", str(pdf_path),
            "--pdf-engine", PDF_ENGINE,
            "--from", "markdown+raw_tex",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def build_docx(md_path: Path, docx_path: Path) -> None:
    subprocess.run(
        [
            "pandoc",
            str(md_path),
            "-o", str(docx_path),
            "--from", "markdown+raw_tex",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


# =============================================================================
# Auto-tune
# =============================================================================

def render_and_count(content: dict, preset: dict, md_path: Path, pdf_path: Path) -> int:
    md = render_markdown(content, preset)
    md_path.write_text(md, encoding="utf-8")
    build_pdf(md_path, pdf_path)
    return count_pdf_pages(pdf_path)


def auto_tune(content: dict, target_pages: int, md_path: Path, pdf_path: Path) -> dict:
    """Binary search for the loosest preset whose page count <= target_pages.
    Returns the chosen preset dict; raises if even the tightest doesn't fit."""

    print(f"Auto-tuning to fit {target_pages} page(s)...")

    # Quick check: does the tightest preset even fit?
    tight_idx = len(PRESETS) - 1
    pages = render_and_count(content, PRESETS[tight_idx], md_path, pdf_path)
    print(f"  trial: {PRESETS[tight_idx]['name']:<12} -> {pages} page(s)")
    if pages > target_pages:
        raise RuntimeError(
            f"Even the tightest preset ('{PRESETS[tight_idx]['name']}') needs {pages} pages. "
            f"Trim some content or add a tighter preset to PRESETS in build_resume.py."
        )

    # Binary search for the smallest index with pages <= target.
    lo, hi = 0, tight_idx
    best_idx = tight_idx
    cache: dict[int, int] = {tight_idx: pages}

    while lo <= hi:
        mid = (lo + hi) // 2
        if mid not in cache:
            pages = render_and_count(content, PRESETS[mid], md_path, pdf_path)
            cache[mid] = pages
            print(f"  trial: {PRESETS[mid]['name']:<12} -> {pages} page(s)")
        pages = cache[mid]
        if pages <= target_pages:
            best_idx = mid
            hi = mid - 1   # try looser
        else:
            lo = mid + 1   # try tighter

    chosen = PRESETS[best_idx]
    print(f"Selected preset: {chosen['name']}  "
          f"(fontsize {chosen['fontsize']}pt, margin {chosen['margin']}in, "
          f"parskip {chosen['parskip']}pt)")

    # Re-render with the chosen preset (in case it wasn't the last attempt).
    if cache.get(best_idx) is None or best_idx != tight_idx:
        render_and_count(content, chosen, md_path, pdf_path)

    return chosen


# =============================================================================
# Main
# =============================================================================

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    p.add_argument(
        "--target-pages", type=int, default=DEFAULT_TARGET_PAGES,
        help=f"Page count to fit when auto-tuning. Default {DEFAULT_TARGET_PAGES}.",
    )
    p.add_argument(
        "--preset",
        choices=[p["name"] for p in PRESETS],
        help="Force a specific preset and skip auto-tuning.",
    )
    p.add_argument(
        "--no-auto", action="store_true",
        help=f"Skip auto-tuning and use the '{DEFAULT_PRESET_NAME}' preset.",
    )
    p.add_argument(
        "--list-presets", action="store_true",
        help="Print the available presets and exit.",
    )
    return p.parse_args()


def find_preset_by_name(name: str) -> dict:
    for p in PRESETS:
        if p["name"] == name:
            return p
    raise KeyError(f"No preset named '{name}'.")


def main() -> None:
    args = parse_args()

    if args.list_presets:
        for p in PRESETS:
            print(f"  {p['name']:<12} fontsize={p['fontsize']}pt "
                  f"margin={p['margin']}in parskip={p['parskip']}pt "
                  f"sec_top={p['sec_top']}pt linespread={p['linespread']}")
        return

    require("pandoc")
    if PDF_ENGINE == "xelatex":
        require("xelatex")

    if not CONTENT_FILE.exists():
        sys.exit(f"ERROR: {CONTENT_FILE} not found.")

    with CONTENT_FILE.open("r", encoding="utf-8") as f:
        content = yaml.safe_load(f)

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    md_path = BUILD_DIR / "resume.md"
    pdf_out = OUT_DIR / "resume.pdf"
    docx_out = OUT_DIR / "resume.docx"

    # ---- Choose preset ----
    if args.preset:
        chosen = find_preset_by_name(args.preset)
        print(f"Using preset '{chosen['name']}' (forced).")
        md = render_markdown(content, chosen)
        md_path.write_text(md, encoding="utf-8")
        print(f"  building {pdf_out}")
        build_pdf(md_path, pdf_out)
    elif args.no_auto:
        chosen = find_preset_by_name(DEFAULT_PRESET_NAME)
        print(f"Using preset '{chosen['name']}' (auto-tune disabled).")
        md = render_markdown(content, chosen)
        md_path.write_text(md, encoding="utf-8")
        print(f"  building {pdf_out}")
        build_pdf(md_path, pdf_out)
    else:
        chosen = auto_tune(content, args.target_pages, md_path, pdf_out)
        # auto_tune already left the PDF at the chosen preset's render.

    # ---- DOCX uses the same preset (its 'pages' are fluid in Word anyway). ----
    print(f"  building {docx_out}")
    build_docx(md_path, docx_out)

    pages = count_pdf_pages(pdf_out)
    print(f"Done. {pdf_out.name}: {pages} page(s); {docx_out.name}: written.")


if __name__ == "__main__":
    main()
