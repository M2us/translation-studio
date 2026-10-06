"""Small offline HTML renderer for UserGuide's headings, paragraphs and inline markup."""
import html
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def inline(value):
    value = html.escape(value)
    value = re.sub(r"`([^`]+)`", r"<code>\1</code>", value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", value)
    value = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', value)
    return re.sub(r'(href="UserGuide(?:\.ru)?)\.md"', r'\1.html"', value)


def render(name, language, title):
    markdown = (ROOT / "Docs" / (name + ".md")).read_text(encoding="utf-8")
    blocks = []
    for block in markdown.strip().split("\n\n"):
        level = len(block) - len(block.lstrip("#"))
        if 1 <= level <= 6:
            blocks.append(f"<h{level}>" + inline(block[level:].strip()) + f"</h{level}>")
        else:
            blocks.append("<p>" + inline(block) + "</p>")
    output = f'<!doctype html><html lang="{language}"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Translation Studio — {title}</title>'
    output += '<style>body{max-width:940px;margin:40px auto;padding:0 24px;background:#f5f7fb;color:#253047;font:16px/1.65 Segoe UI,sans-serif}h1,h2{color:#244ca9}h2{margin-top:2em}code{background:#eaf0f8;padding:2px 5px;border-radius:3px}a{color:#355ece}</style>'
    (ROOT / "Docs" / (name + ".html")).write_text(output + "\n".join(blocks) + "</html>", encoding="utf-8")


def main():
    render("UserGuide", "en", "user guide")
    render("UserGuide.ru", "ru", "руководство")


if __name__ == "__main__":
    main()
