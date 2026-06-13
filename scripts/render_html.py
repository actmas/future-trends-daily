#!/usr/bin/env python3
"""
Render site/reports/<date>.html + site/index.html from data/<date>.json.
Inline CSS, system fonts, dark theme with light auto-switch. No external deps.
"""
from __future__ import annotations

import html
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
DATA = PROJECT / "data"
SITE = PROJECT / "site"
REPORTS = SITE / "reports"
SITE.mkdir(exist_ok=True)
REPORTS.mkdir(exist_ok=True)

BJ = timezone(timedelta(hours=8))
TODAY = datetime.now(BJ).strftime("%Y-%m-%d")
TIMESTAMP = datetime.now(BJ).strftime("%Y-%m-%d %H:%M 北京时间")

CATEGORY_ICON = {
    "电商": "🛒", "AI": "🤖", "SaaS": "⚙️", "内容": "📹",
    "服务": "🤝", "硬件": "🔧", "其他": "💡",
}
HEAT_COLOR = {"升温中": "#f59e0b", "爆发期": "#ef4444", "降温中": "#64748b"}
COST_COLOR = {"低": "#10b981", "中": "#f59e0b", "高": "#ef4444"}
TIME_COLOR = {"1-3月": "#10b981", "3-6月": "#f59e0b", "6-12月": "#64748b"}


CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg: #0a0e1a; --bg-2: #131826; --bg-3: #1c2235;
  --text: #e8eaf0; --text-2: #9ca3af; --text-3: #6b7280;
  --accent: #6366f1; --accent-2: #8b5cf6;
  --border: rgba(255,255,255,0.08);
  --shadow: 0 4px 24px rgba(0,0,0,0.3);
}
@media (prefers-color-scheme: light) {
  :root { --bg: #f8fafc; --bg-2: #ffffff; --bg-3: #f1f5f9;
          --text: #0f172a; --text-2: #475569; --text-3: #94a3b8;
          --border: rgba(0,0,0,0.08);
          --shadow: 0 4px 24px rgba(0,0,0,0.06); }
}
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
       "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
       background: var(--bg); color: var(--text); line-height: 1.6;
       min-height: 100vh; }
.container { max-width: 1200px; margin: 0 auto; padding: 32px 20px 80px; }
.hero { background: linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%);
        border-radius: 20px; padding: 40px 32px; margin-bottom: 32px;
        color: #fff; box-shadow: var(--shadow); position: relative; overflow: hidden; }
.hero::before { content: "📡"; position: absolute; top: -20px; right: -10px;
                font-size: 200px; opacity: 0.12; transform: rotate(15deg); }
.hero h1 { font-size: 32px; font-weight: 800; margin-bottom: 8px;
          position: relative; letter-spacing: -0.5px; }
.hero .sub { font-size: 16px; opacity: 0.92; position: relative; }
.hero .meta { font-size: 13px; opacity: 0.75; margin-top: 12px; position: relative; }
.section { margin-bottom: 36px; }
.section h2 { font-size: 20px; font-weight: 700; margin-bottom: 18px;
              color: var(--text); display: flex; align-items: center; gap: 10px; }
.section h2 .badge { font-size: 11px; background: var(--accent); color: #fff;
                    padding: 3px 10px; border-radius: 10px; font-weight: 600; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: 18px; }
.card { background: var(--bg-2); border: 1px solid var(--border);
        border-radius: 14px; padding: 20px; box-shadow: var(--shadow);
        transition: transform 0.15s, box-shadow 0.15s; }
.card:hover { transform: translateY(-2px); box-shadow: 0 8px 32px rgba(0,0,0,0.4); }
.card .title { font-size: 16px; font-weight: 700; margin-bottom: 8px; color: var(--text); }
.card .desc { font-size: 13px; color: var(--text-2); line-height: 1.55; }
.tag { display: inline-block; font-size: 11px; padding: 3px 10px;
       border-radius: 10px; background: var(--bg-3); color: var(--text-2);
       margin-right: 6px; margin-top: 4px; font-weight: 500; }
.tag.heat { color: #fff; font-weight: 600; }
.theme-card { background: var(--bg-2); border: 1px solid var(--border);
              border-left: 3px solid var(--accent); border-radius: 12px;
              padding: 18px 20px; box-shadow: var(--shadow); }
.theme-card .name { font-size: 16px; font-weight: 700; margin-bottom: 8px; }
.theme-card .evidence { font-size: 13px; color: var(--text-2); }
.opp-card { background: var(--bg-2); border: 1px solid var(--border);
            border-radius: 14px; padding: 22px; box-shadow: var(--shadow);
            position: relative; }
.opp-card .head { display: flex; align-items: flex-start; gap: 12px;
                  margin-bottom: 12px; }
.opp-card .icon { font-size: 32px; line-height: 1; flex-shrink: 0; }
.opp-card .title { font-size: 17px; font-weight: 700; flex: 1; line-height: 1.4; }
.opp-card .meta { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.opp-card .meta .pill { font-size: 11px; padding: 4px 10px; border-radius: 12px;
                       font-weight: 600; color: #fff; }
.opp-card .rationale { font-size: 13.5px; color: var(--text-2); line-height: 1.65; }
.flag-card { background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.3);
             border-radius: 12px; padding: 14px 18px; }
.flag-card .item { font-size: 13.5px; color: var(--text); margin: 4px 0; }
.sources { background: var(--bg-2); border: 1px solid var(--border);
           border-radius: 14px; padding: 18px 22px; }
.sources h3 { font-size: 14px; font-weight: 700; margin-bottom: 12px; color: var(--text); }
.sources .src { font-size: 12.5px; color: var(--text-2); padding: 4px 0;
                border-bottom: 1px dashed var(--border); }
.sources .src:last-child { border-bottom: none; }
.sources .src .lbl { display: inline-block; min-width: 90px; font-weight: 600;
                    color: var(--text); }
.sources .src a { color: var(--accent); text-decoration: none; }
.sources .src a:hover { text-decoration: underline; }
.archives { background: var(--bg-2); border: 1px solid var(--border);
            border-radius: 14px; padding: 18px 22px; margin-top: 24px; }
.archives h3 { font-size: 14px; font-weight: 700; margin-bottom: 12px; }
.archives ul { list-style: none; }
.archives li { padding: 4px 0; font-size: 13px; }
.archives a { color: var(--accent); text-decoration: none; }
.archives a:hover { text-decoration: underline; }
.footer { text-align: center; color: var(--text-3); font-size: 12px;
          margin-top: 48px; padding-top: 24px; border-top: 1px solid var(--border); }
@media (max-width: 640px) {
  .hero h1 { font-size: 24px; }
  .grid { grid-template-columns: 1fr; }
  .opp-card .head { flex-direction: column; }
}
"""


def esc(s: str) -> str:
    return html.escape(s or "")


def render_themes(analysis: dict) -> str:
    out = []
    for t in analysis.get("themes", []):
        heat = t.get("heat", "升温中")
        color = HEAT_COLOR.get(heat, "#64748b")
        out.append(f"""
<div class="theme-card">
  <div class="name">{esc(t.get("name", ""))} <span class="tag heat" style="background:{color}">{esc(heat)}</span></div>
  <div class="evidence">{esc(t.get("evidence", ""))}</div>
</div>""")
    return "\n".join(out)


def render_opportunities(analysis: dict) -> str:
    out = []
    for o in analysis.get("opportunities", []):
        cat = o.get("category", "其他")
        icon = CATEGORY_ICON.get(cat, "💡")
        cost = o.get("entry_cost", "中")
        time_ = o.get("time_to_cash", "3-6月")
        cost_c = COST_COLOR.get(cost, "#64748b")
        time_c = TIME_COLOR.get(time_, "#64748b")
        out.append(f"""
<div class="opp-card">
  <div class="head">
    <div class="icon">{icon}</div>
    <div class="title">{esc(o.get("title", ""))}</div>
  </div>
  <div class="meta">
    <span class="pill" style="background:var(--accent)">{esc(cat)}</span>
    <span class="pill" style="background:{cost_c}">门槛 {esc(cost)}</span>
    <span class="pill" style="background:{time_c}">回本 {esc(time_)}</span>
  </div>
  <div class="rationale">{esc(o.get("rationale", ""))}</div>
</div>""")
    return "\n".join(out)


def render_flags(analysis: dict) -> str:
    if not analysis.get("red_flags"):
        return ""
    items = "".join(f'<div class="item">⚠️ {esc(f)}</div>'
                    for f in analysis["red_flags"])
    return f'<div class="flag-card">{items}</div>'


def render_sources(payload: dict) -> str:
    src = payload.get("sources", {})
    rows = []
    label_map = {
        "reddit_top": ("Reddit Top (24h)", "https://reddit.com"),
        "hackernews_top": ("Hacker News", "https://news.ycombinator.com"),
        "reuters_world": ("Reuters World", "https://www.reuters.com"),
        "bbc_business": ("BBC Business", "https://www.bbc.com/news/business"),
        "github_trending": ("GitHub Trending", "https://github.com/trending"),
        "producthunt_today": ("Product Hunt", "https://www.producthunt.com"),
    }
    for k, (lbl, url) in label_map.items():
        n = len(src.get(k, []))
        if n > 0:
            rows.append(
                f'<div class="src"><span class="lbl">{esc(lbl)}</span>'
                f'<a href="{url}" target="_blank" rel="noopener">{n} 条</a></div>'
            )
    if not rows:
        rows.append('<div class="src" style="color:var(--text-3)">本轮无源数据,沿用上次分析</div>')
    return f'<div class="sources"><h3>📡 本轮抓取源</h3>{"".join(rows)}</div>'


def render_github_signals(payload: dict) -> str:
    """Show the GitHub trending repos as cards — useful for spotting tech wind."""
    gh = payload.get("sources", {}).get("github_trending", [])
    if not gh:
        return ""
    out = ['<div class="grid">']
    for g in gh[:9]:
        out.append(f"""
<div class="card">
  <div class="title"><a href="{esc(g.get('url', '#'))}" target="_blank" rel="noopener" style="color:inherit;text-decoration:none">{esc(g.get('name', ''))}</a></div>
  <div class="desc">{esc((g.get('description') or '')[:200])}</div>
</div>""")
    out.append("</div>")
    return "\n".join(out)


def render_bbc_signals(payload: dict) -> str:
    bbc = payload.get("sources", {}).get("bbc_business", [])
    if not bbc:
        return ""
    out = ['<div class="grid">']
    for b in bbc[:9]:
        out.append(f"""
<div class="card">
  <div class="title">{esc(b.get('title', '')[:120])}</div>
  <div class="desc">来源: BBC Business</div>
</div>""")
    out.append("</div>")
    return "\n".join(out)


def render_html(payload: dict, archives: list[str]) -> str:
    analysis = payload.get("analysis", {})
    themes = render_themes(analysis)
    opps = render_opportunities(analysis)
    flags = render_flags(analysis)
    sources = render_sources(payload)
    gh = render_github_signals(payload)
    bbc = render_bbc_signals(payload)

    arch_html = ""
    if archives:
        items = "".join(
            f'<li><a href="reports/{a}.html">{a}</a></li>'
            for a in archives[:30]
        )
        arch_html = f'<div class="archives"><h3>🗂 历史报告</h3><ul>{items}</ul></div>'

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>未来风口雷达 · {TODAY}</title>
<style>{CSS}</style>
</head>
<body>
<div class="container">
  <div class="hero">
    <h1>📡 未来风口雷达</h1>
    <div class="sub">基于国际电商 / 国际局势 / 社交媒体 / 技术社区的实时信号</div>
    <div class="meta">{TIMESTAMP} · 多源抓取 + LLM 机会分析</div>
  </div>

  <div class="section">
    <h2>🌐 主流趋势主题 <span class="badge">AI 解读</span></h2>
    <div class="grid">
{themes}
    </div>
  </div>

  <div class="section">
    <h2>💰 可落地的赚钱机会 <span class="badge">{len(analysis.get('opportunities', []))} 个</span></h2>
    {opps}
  </div>

  {f'<div class="section"><h2>🚫 伪风口预警</h2>{flags}</div>' if flags else ""}

  <div class="section">
    <h2>📈 GitHub 风向标 <span class="badge">技术爆款</span></h2>
    {gh}
  </div>

  <div class="section">
    <h2>📰 BBC 商业头条 <span class="badge">国际局势</span></h2>
    {bbc}
  </div>

  <div class="section">
    <h2>📡 数据源</h2>
    {sources}
  </div>

  {arch_html}

  <div class="footer">
    Generated by Hermes Agent · 每日北京时间 12:00 自动生成 · 本看板为信息整合,非投资建议
  </div>
</div>
</body>
</html>"""


def main():
    in_path = DATA / f"{TODAY}.json"
    if not in_path.exists():
        sys.exit(f"missing {in_path}")
    payload = json.loads(in_path.read_text())

    # All available archives
    archives = sorted([p.stem for p in REPORTS.glob("*.html") if p.stem != "index"], reverse=True)
    if TODAY not in archives:
        archives.insert(0, TODAY)

    html_doc = render_html(payload, archives)

    (REPORTS / f"{TODAY}.html").write_text(html_doc)
    (SITE / "index.html").write_text(html_doc)
    (SITE / ".nojekyll").write_text("")
    print(f"✓ wrote {REPORTS / f'{TODAY}.html'} and site/index.html")


if __name__ == "__main__":
    main()
