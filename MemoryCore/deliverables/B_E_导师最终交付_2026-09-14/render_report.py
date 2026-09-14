"""Compose and render the final B+E mentor report as white-background HTML/PDF."""

from __future__ import annotations

from pathlib import Path
import html
import re

from markdown_it import MarkdownIt
from weasyprint import HTML


HERE = Path(__file__).resolve().parent
BENCHMARKS = HERE.parents[1] / "benchmarks"
CORE_REPORT = BENCHMARKS / "B_E_FINAL_SUBMISSION_REPORT_2026-09-14.md"
PRELUDE = HERE / "report_prelude.md"
APPENDICES = HERE / "report_appendices.md"
MARKDOWN_OUTPUT = HERE / "B_E_方案介绍与测试结论报告.md"
HTML_OUTPUT = HERE / "B_E_方案介绍与测试结论报告.html"
PDF_OUTPUT = HERE / "B_E_方案介绍与测试结论报告.pdf"


CSS = r"""
@font-face { font-family: ReportSans; src: url("file:///usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"); }
@font-face { font-family: ReportSerif; src: url("file:///usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"); }
@page {
  size: A4; margin: 18mm 17mm 18mm;
  @top-left { content: "题目三 · B+E 方案介绍与测试结论"; font: 7.3pt ReportSans; color: #667085; }
  @top-right { content: "2026-09-14"; font: 7.3pt ReportSans; color: #667085; }
  @bottom-center { content: counter(page); font: 8pt ReportSans; color: #667085; }
}
@page:first { @top-left { content: none; } @top-right { content: none; } @bottom-center { content: none; } }
* { box-sizing: border-box; }
html, body { background: #fff; color: #172033; }
body { margin: 0; font: 9pt/1.68 ReportSans, sans-serif; }
main { max-width: 176mm; margin: 0 auto; }
a { color: #215bb5; text-decoration: none; overflow-wrap: anywhere; }
p { margin: 0 0 3.2mm; orphans: 3; widows: 3; }
h1, h2, h3 { break-after: avoid; }
h1 { margin: 9mm 0 4mm; padding-bottom: 2mm; border-bottom: .35mm solid #cfd8e6;
  color: #102a56; font: 700 16pt/1.3 ReportSerif, serif; }
h2 { margin: 6mm 0 2.5mm; color: #183b72; font: 700 11.5pt/1.35 ReportSans, sans-serif; }
h3 { margin: 4mm 0 2mm; color: #24466f; font-size: 9.8pt; }
ul, ol { margin: 1mm 0 4mm; padding-left: 6mm; }
li { margin: 1mm 0; }
strong { color: #111827; }
code { font: 7.7pt "DejaVu Sans Mono", monospace; background: #eef2f7; color: #26364f;
  padding: .2mm .8mm; border-radius: .7mm; overflow-wrap: anywhere; }
pre { margin: 3mm 0 5mm; padding: 3.5mm 4.5mm; border-radius: 1.5mm; color: #eaf0fa;
  background: #17243a; font: 7.1pt/1.5 "DejaVu Sans Mono", monospace; white-space: pre-wrap; break-inside: avoid; }
pre code { padding: 0; color: inherit; background: transparent; }
table { width: 100%; margin: 2.5mm 0 5mm; border-collapse: collapse; font-size: 7.35pt;
  line-height: 1.42; break-inside: avoid; }
th, td { padding: 1.8mm 2mm; border: .22mm solid #d6dee9; vertical-align: top; }
th { background: #eaf0f8; color: #163866; text-align: left; font-weight: 700; }
tbody tr:nth-child(even) td { background: #f8fafc; }
blockquote { margin: 3.5mm 0 5mm; padding: 3mm 4mm; border-left: 1.1mm solid #3c72c4;
  background: #f1f5fb; color: #33445e; }
hr { margin: 8mm 0; border: 0; border-top: .3mm solid #d5dce7; }
.page-break { page-break-after: always; height: 0; }
.cover { height: 250mm; padding: 25mm 7mm 10mm; display: flex; flex-direction: column;
  justify-content: flex-start; background: #fff; color: #15223a; }
.cover h1 { margin: 12mm 0 5mm; padding: 0; border: 0; color: #10284f;
  font: 700 26pt/1.28 ReportSerif, serif; }
.cover-kicker { color: #315f9f; font-size: 10pt; letter-spacing: 1.7mm; font-weight: 700; }
.cover-subtitle { color: #244c82; font-size: 13pt; line-height: 1.65; }
.cover-rule { width: 42mm; margin: 13mm 0 8mm; border-top: 1.4mm solid #2d64ad; }
.cover-type { color: #132f5c; font-size: 16pt; font-weight: 700; }
.cover > p { width: 125mm; margin-top: 5mm; color: #55657d; font-size: 10pt; }
.cover-meta { margin-top: auto; width: 142mm; border-top: .3mm solid #cbd5e1; padding-top: 5mm; }
.cover-meta div { display: grid; grid-template-columns: 27mm 1fr; margin: 2mm 0; font-size: 8.5pt; }
.cover-meta span { color: #7b8799; } .cover-meta b { color: #243650; font-weight: 500; }
.key-results { display: grid; grid-template-columns: repeat(4, 1fr); gap: 3mm; margin: 6mm 0 8mm; }
.key-results div { padding: 4mm 2mm; border: .3mm solid #c8d5e6; border-radius: 1.5mm; text-align: center; background: #f7f9fc; }
.key-results b { display: block; color: #174e91; font-size: 15pt; }
.key-results span { display: block; margin-top: 1mm; color: #5a687c; font-size: 7.3pt; line-height: 1.45; }
.flow-diagram { display: grid; grid-template-columns: 1fr 5mm 1fr 5mm 1fr 5mm 1fr 5mm 1fr;
  gap: 1.5mm; align-items: center; margin: 5mm 0 7mm; padding: 4mm; border: .3mm solid #ccd7e5;
  background: #f8fafc; break-inside: avoid; }
.flow-diagram div { padding: 3mm 2mm; border: .25mm solid #c2d1e5; border-radius: 1mm; text-align: center; background: #fff; }
.flow-diagram b, .flow-diagram span { display: block; }
.flow-diagram b { color: #194d8c; font-size: 8pt; }
.flow-diagram span { margin-top: 1mm; color: #627085; font-size: 6.8pt; line-height: 1.35; }
.flow-diagram i { color: #4976ad; text-align: center; font-style: normal; }
.toc { columns: 2; column-gap: 12mm; margin: 4mm 0 10mm; }
.toc a { display: flex; gap: 2mm; margin: 1.7mm 0; color: #263b5b; font-size: 8.4pt; break-inside: avoid; }
.toc a span:first-child { flex: 1; border-bottom: .2mm dotted #c0c9d7; }
.toc a span:last-child::after { content: target-counter(attr(data-href), page); }
.source-note { color: #697586; font-size: 7.5pt; }
"""


def core_body() -> str:
    source = CORE_REPORT.read_text(encoding="utf-8")
    marker = "## 1. 完成的工作与主要贡献"
    if marker not in source:
        raise RuntimeError("core report structure changed")
    body = marker + source.split(marker, 1)[1]
    body = re.sub(r"^## ", "# ", body, flags=re.M)
    body = re.sub(r"^### ", "## ", body, flags=re.M)
    return body


def compose() -> str:
    return "\n".join([
        PRELUDE.read_text(encoding="utf-8").rstrip(),
        core_body().rstrip(),
        APPENDICES.read_text(encoding="utf-8").rstrip(),
        "",
    ])


def add_headings_and_toc(body: str) -> str:
    entries: list[tuple[str, str]] = []
    counter = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal counter
        level, content = match.group(1), match.group(2)
        plain = re.sub(r"<[^>]+>", "", content)
        plain = html.unescape(plain).strip()
        counter += 1
        anchor = f"section-{counter}"
        if re.match(r"^(?:\d+\.|附录)", plain):
            entries.append((anchor, plain))
        return f'<h{level} id="{anchor}">{content}</h{level}>'

    body = re.sub(r"<h([12])>(.*?)</h\1>", replace, body, flags=re.S)
    toc = '<div class="toc">' + "".join(
        f'<a href="#{anchor}"><span>{html.escape(title)}</span><span data-href="#{anchor}"></span></a>'
        for anchor, title in entries
    ) + "</div>"
    return body.replace("<!--AUTO_TOC-->", toc)


def main() -> None:
    source = compose()
    MARKDOWN_OUTPUT.write_text(source, encoding="utf-8")
    md = MarkdownIt("commonmark", {"html": True, "linkify": True}).enable("table")
    body = add_headings_and_toc(md.render(source))
    document = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>面向多轮交互式长编程任务的记忆自优化：B+E 方案介绍与测试结论</title>
<style>{CSS}</style></head><body><main>{body}</main></body></html>'''
    HTML_OUTPUT.write_text(document, encoding="utf-8")
    rendered = HTML(string=document, base_url=str(HERE)).render()
    rendered.write_pdf(PDF_OUTPUT, pdf_version="1.4", uncompressed_pdf=False)
    print(f"Rendered {len(rendered.pages)} pages: {PDF_OUTPUT}")


if __name__ == "__main__":
    main()
