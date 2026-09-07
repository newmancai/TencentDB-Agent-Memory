"""Render the internal TDAI Memory assignment report to HTML and PDF."""

from pathlib import Path
import html
import re

from markdown_it import MarkdownIt
from weasyprint import HTML


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "Anchor_技术报告.md"
HTML_OUTPUT = HERE / "Anchor_技术报告.html"
PDF_OUTPUT = HERE / "Anchor_技术报告.pdf"
PROJECT_URL = "https://github.com/newmancai/TencentDB-Agent-Memory/tree/feat/anchor-memory"
COMMIT_URL = "https://github.com/newmancai/TencentDB-Agent-Memory/commit/69486006e02800ad1a686399b4c0a6cfbf9acb70"


CSS = r"""
@font-face { font-family: AnchorSans; src: url("file:///usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"); }
@font-face { font-family: AnchorSerif; src: url("file:///usr/share/fonts/truetype/arphic-gbsn00lp/gbsn00lp.ttf"); }
@page {
  size: A4;
  margin: 18mm 17mm 18mm 17mm;
  @top-left { content: "TDAI MEMORY · 内部技术作业"; font: 7.5pt AnchorSans; color: #626a75; }
  @top-right { content: "2026-09-07"; font: 7.5pt AnchorSans; color: #7c8798; }
  @bottom-center { content: counter(page); font: 8pt AnchorSans; color: #7c8798; }
}
* { box-sizing: border-box; }
html { color: #18202b; background: white; }
body { margin: 0; font-family: AnchorSans, "DejaVu Sans", sans-serif; font-size: 9.15pt; line-height: 1.67; }
a { color: #2d63c8; text-decoration: none; overflow-wrap: anywhere; }
main { max-width: 176mm; margin: 0 auto; }
h1 { font-family: AnchorSerif, serif; font-size: 21pt; line-height: 1.25; color: #111722; border-bottom: .4mm solid #d6dce5; padding-bottom: 3mm; margin: 0 0 7mm; }
h2 { font-family: AnchorSerif, serif; font-size: 15pt; line-height: 1.3; margin: 9mm 0 3.5mm; color: #172b54; break-after: avoid; }
h3 { font-size: 10.5pt; margin: 6mm 0 2mm; color: #233d72; break-after: avoid; }
p { margin: 0 0 3.5mm; orphans: 3; widows: 3; }
ul, ol { padding-left: 6mm; margin: 1mm 0 4mm; }
li { margin: 1.2mm 0; }
strong { color: #111722; }
code { font-family: "DejaVu Sans Mono", monospace; font-size: 8.2pt; background: #eef2f7; color: #273650; padding: .2mm 1mm; border-radius: 1mm; }
pre { font-family: "DejaVu Sans Mono", monospace; font-size: 7.4pt; line-height: 1.55; color: #e8edf8; background: #162033; padding: 4mm 5mm; border-radius: 2mm; white-space: pre-wrap; break-inside: avoid; }
pre code { background: transparent; color: inherit; padding: 0; }
table { width: 100%; border-collapse: collapse; margin: 3mm 0 6mm; font-size: 7.8pt; line-height: 1.42; break-inside: avoid; }
th { background: #eaf0fb; color: #213963; font-weight: 700; text-align: left; }
th, td { border: .25mm solid #d6dce5; padding: 2.2mm 2.4mm; vertical-align: top; }
tbody tr:nth-child(even) td { background: #f8fafc; }
blockquote { margin: 4mm 0; padding: 3mm 4mm; border-left: 1.2mm solid #5f82d6; background: #f1f5fc; color: #33435e; }
.keyline { margin: 6mm 0 8mm; padding: 4mm 5mm; border: .35mm solid #b9c8e7; border-radius: 2mm; background: #f4f7fd; }
.mono { font-family: "DejaVu Sans Mono", monospace; font-size: 7.5pt; color: #526075; }
.figure { margin: 5mm 0 7mm; padding: 4mm 5mm; background: #f8fafc; border: .3mm solid #dbe1e9; border-radius: 2mm; break-inside: avoid; }
.figure-title { font-weight: 700; color: #213963; margin-bottom: 3mm; }
.bar-row { display: grid; grid-template-columns: 36mm 1fr 18mm; align-items: center; gap: 3mm; margin: 2mm 0; font-size: 8pt; }
.bar-row i { display: block; height: 4mm; min-width: 1mm; background: #b35e5e; border-radius: 2mm; }
.bar-row.good i { background: #4c78cf; }
.bar-row b { text-align: right; }
.figure-note { margin-top: 3mm; color: #69768a; font-size: 7.4pt; }
hr { border: 0; border-top: .3mm solid #d6dce5; margin: 8mm 0; }
.report-body > h2 { page-break-before: auto; }
"""


def render_markdown(source: str) -> str:
    md = MarkdownIt("commonmark", {"html": True, "linkify": True}).enable("table")
    return md.render(source)


def main() -> None:
    body = render_markdown(SOURCE.read_text(encoding="utf-8"))
    body = re.sub(r"<h([123])>(.*?)</h\1>", lambda m: f'<h{m.group(1)}>{m.group(2)}</h{m.group(1)}>', body)
    document = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>TDAI Memory 零显式反馈优化</title><style>{CSS}</style></head>
<body>
<main class="report-body">{body}</main>
</body></html>"""
    HTML_OUTPUT.write_text(document, encoding="utf-8")
    rendered = HTML(string=document, base_url=str(HERE)).render()
    rendered.write_pdf(PDF_OUTPUT, pdf_version="1.4", uncompressed_pdf=True)
    print(f"Rendered {len(rendered.pages)} pages: {PDF_OUTPUT}")


if __name__ == "__main__":
    main()
