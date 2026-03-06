#!/usr/bin/env python3
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTICLES = ROOT / 'playground' / 'data' / 'articles.json'
OUTDIR = ROOT / 'playground' / 'output'


def main():
    articles = json.loads(ARTICLES.read_text(encoding='utf-8')) if ARTICLES.exists() else []
    today = datetime.utcnow().strftime('%Y-%m-%d')
    title = f"本周 AI 与机器人动态（降级版）- {today}"

    top = articles[:20]
    lines = [f"---\ntitle: \"{title}\"\n---\n", f"## 📮 {today} 简报（降级生成）\n"]
    lines.append("由于上游模型配额/可用性限制，本期使用 RSS 基础聚合模式生成。\n")
    for i, a in enumerate(top, 1):
        lines.append(f"### {i}. {a.get('title','(no title)')}\n")
        detail = (a.get('detailContent') or '').strip()
        if detail:
            lines.append(detail[:280] + ('...' if len(detail) > 280 else '') + "\n")
        if a.get('url'):
            lines.append(f"来源：{a['url']}\n")

    md = "\n".join(lines)

    html_items = []
    for i, a in enumerate(top, 1):
        t = a.get('title', '(no title)')
        u = a.get('url', '#')
        d = (a.get('detailContent') or '').strip()
        html_items.append(f"<h3>{i}. {t}</h3><p>{d}</p><p><a href=\"{u}\" target=\"_blank\">来源链接</a></p>")

    html = f"""<!doctype html>
<html><head><meta charset='utf-8'><title>{title}</title></head>
<body style='font-family:Arial,Helvetica,sans-serif;max-width:900px;margin:20px auto;line-height:1.6'>
<h1>{title}</h1>
<p>由于上游模型配额/可用性限制，本期使用 RSS 基础聚合模式生成。</p>
{''.join(html_items)}
</body></html>"""

    usage = """# Token Usage Report

| Metric | Value |
|--------|-------|
| Provider | fallback |
| Model | none |
| Input Tokens | 0 |
| Output Tokens | 0 |
| Total Tokens | 0 |
"""

    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / 'newsletter.md').write_text(md, encoding='utf-8')
    (OUTDIR / 'newsletter.html').write_text(html, encoding='utf-8')
    (OUTDIR / 'usage.md').write_text(usage, encoding='utf-8')
    print('fallback output generated')


if __name__ == '__main__':
    main()
