"""Build the M5 report PDF from report.md (official-template structure).

Usage (from app/):  python3 report/build_pdf.py
Output: report/Receipts_Not_Reports.pdf (+ report.html intermediate).

Page-count rule (per sprint Guidelines): the main body — title through
Conclusion / Code and Data — must be 4-8 pages, not counting References
and appendices. This script renders the body separately to measure it,
then renders the full document, and fails loudly if the body is outside
4-8 pages. Numbers in the report are checked separately by
tests/test_report.py against experiments/results/sweep.json.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from markdown_it import MarkdownIt
from weasyprint import HTML

HERE = Path(__file__).resolve().parent
APP = HERE.parent
MD_PATH = HERE / "report.md"
HTML_PATH = HERE / "report.html"
PDF_PATH = HERE / "Receipts_Not_Reports.pdf"
FIGURE = APP / "experiments" / "results" / "sweep.png"

CSS = """
@page {
  size: Letter;
  margin: 2cm 2.3cm 2.2cm 2.3cm;
  @bottom-center {
    content: "Receipts, Not Reports \\2014  Swarm Alignment Hackathon, November 2026  \\2014  " counter(page);
    font-family: "DejaVu Sans", sans-serif; font-size: 8pt; color: #666;
  }
}
@page :first { @bottom-center { content: ""; } }
body { font-family: "DejaVu Serif", serif; font-size: 10.5pt; line-height: 1.42; color: #111; }
h1 { font-family: "DejaVu Sans", sans-serif; font-size: 20pt; text-align: center; margin: 0.2em 0 0.4em; line-height: 1.25; }
h2 { font-family: "DejaVu Sans", sans-serif; font-size: 13pt; margin: 1.1em 0 0.4em; break-after: avoid; }
h2.refs, h2.appx { break-before: page; }
p { margin: 0.45em 0; text-align: justify; }
p.author-block { text-align: center; }
strong { font-weight: bold; }
em { font-style: italic; }
table { border-collapse: collapse; margin: 0.8em auto; font-size: 9.5pt; width: 100%; }
th, td { border: 0.5pt solid #999; padding: 3pt 5pt; text-align: center; }
th { background: #eee; font-family: "DejaVu Sans", sans-serif; }
td:first-child, th:first-child { text-align: left; }
img { max-width: 100%; display: block; margin: 0.8em auto; }
code { font-family: "DejaVu Sans Mono", monospace; font-size: 9pt; background: #f4f4f4; padding: 0 2pt; }
pre { background: #f4f4f4; padding: 8pt; font-size: 9pt; line-height: 1.4; white-space: pre-wrap; }
pre code { background: none; padding: 0; }
ol, ul { margin: 0.4em 0; padding-left: 1.4em; }
li { margin: 0.25em 0; text-align: justify; }
"""

MD = MarkdownIt("commonmark").enable("table")


def render(md_text: str) -> str:
    """Markdown -> full HTML document. The figure path is made absolute.

    Note: markdown-it cannot parse a ``file://`` link destination, and
    WeasyPrint cannot load a bare absolute path, so the figure is first
    rendered with the plain path and the ``<img src>`` is rewritten to a
    ``file://`` URL in the HTML afterwards.
    """
    md_text = md_text.replace("](sweep.png)", f"]({FIGURE})")
    body = MD.render(md_text)
    body = body.replace(f'src="{FIGURE}"', f'src="file://{FIGURE}"', 1)
    # Centre the title block lines and page-break before References/Appendix A.
    body = body.replace(
        "<h2>References</h2>", '<h2 class="refs">References</h2>', 1
    )
    body = body.replace(
        "<h2>Appendix A.",
        '<h2 class="appx">Appendix A.',
        1,
    )
    return f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>"


def page_count(html: str) -> int:
    return len(HTML(string=html).render().pages)


def main() -> int:
    md_text = MD_PATH.read_text()
    if not FIGURE.exists():
        print(f"missing figure: {FIGURE}", file=sys.stderr)
        return 1
    full_html = render(md_text)
    HTML_PATH.write_text(full_html)
    # Body = everything before the References heading (excluded from the count).
    body_md = md_text.split("## References")[0]
    body_pages = page_count(render(body_md))
    full_doc = HTML(string=full_html).render()
    total_pages = len(full_doc.pages)
    print(f"body pages (excl. references/appendices): {body_pages}")
    print(f"total pages (incl. references/appendices): {total_pages}")
    if not 4 <= body_pages <= 8:
        print(
            f"FAIL: body must be 4-8 pages, got {body_pages}",
            file=sys.stderr,
        )
        return 1
    full_doc.write_pdf(str(PDF_PATH))
    print(f"wrote {PDF_PATH} ({PDF_PATH.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
