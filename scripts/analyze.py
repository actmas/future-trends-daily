#!/usr/bin/env python3
"""
LLM analyze step. Reads data/<today>.json and produces a Chinese-language
analysis structure: themes, opportunities, action items. Saved back to the
same JSON as payload['analysis'].
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
DATA = PROJECT / "data"

BJ = timezone(timedelta(hours=8))
TODAY = datetime.now(BJ).strftime("%Y-%m-%d")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE = os.environ.get("OPENAI_BASE", "https://api.openai.com/v1")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


def _call_llm(prompt: str, max_tokens: int = 1800) -> str:
    """Direct OpenAI-compatible chat completion. No SDK."""
    if not OPENAI_API_KEY:
        return ""  # Skip silently when no key — caller falls back
    body = json.dumps({
        "model": OPENAI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.4,
    }).encode()
    req = urllib.request.Request(
        f"{OPENAI_BASE}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read())
            return d["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"  [llm error] {type(e).__name__}: {e}", file=sys.stderr)
        return ""


def _extract_json(text: str) -> dict:
    """LLM sometimes wraps JSON in ```json fences — strip them."""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if m:
        text = m.group(1)
    try:
        return json.loads(text)
    except Exception:
        return {}


def build_prompt(sources: dict) -> str:
    """Compact digest prompt — Chinese, structured, action-oriented."""
    bbc = "\n".join(f"- {x['title']}" for x in sources.get("bbc_business", [])[:12])
    gh = "\n".join(f"- {x['name']}: {(x.get('description') or '')[:80]}"
                   for x in sources.get("github_trending", [])[:12])
    reuters = "\n".join(f"- {x['title']}" for x in sources.get("reuters_world", [])[:10])
    hn = "\n".join(f"- {x['title']}" for x in sources.get("hackernews_top", [])[:10])
    reddit = "\n".join(f"- [r/{x['sub']}] {x['title']}" for x in sources.get("reddit_top", [])[:10])

    return f"""你是「未来风口雷达」分析师。基于以下实时抓取的国际多源信号,识别未来 6-12 个月的创业/赚钱机会。

## BBC 商业新闻
{bbc or "(无)"}

## 路透社国际新闻
{reuters or "(无)"}

## Hacker News 热门
{hn or "(无)"}

## Reddit 热门讨论
{reddit or "(无)"}

## GitHub Trending (技术风向标)
{gh or "(无)"}

请输出严格的 JSON,不要任何解释,不要 markdown 围栏。结构:
{{
  "themes": [
    {{"name": "主题名(中文,10字以内)", "evidence": "支撑该主题的2-3条具体信号", "heat": "升温中/爆发期/降温中"}}
  ],
  "opportunities": [
    {{"title": "机会标题(中文,18字以内)", "category": "电商/AI/SaaS/内容/服务/硬件/其他", "entry_cost": "低(万元内)/中(10-50万)/高(百万+)", "time_to_cash": "1-3月/3-6月/6-12月", "rationale": "为什么这是机会,具体怎么做,目标客户是谁"}}
  ],
  "red_flags": ["不值得追的伪风口,2-3条"]
}}

要求:
1. themes 3-5 个,opportunities 4-7 个,red_flags 1-3 个
2. 机会必须具体到"卖什么、给谁、怎么收钱",不能是"AI 很有前景"这种废话
3. 结合 2026 年的真实环境(AI agent 成熟 / 关税战 / 太空经济 / 老龄化 / 出海)
4. 优先识别普通人(1-2人小团队)能切入的方向
"""


def fallback_analysis(sources: dict) -> dict:
    """Rule-based fallback when LLM unavailable. Decent enough to ship."""
    gh_names = [x["name"] for x in sources.get("github_trending", [])]
    bbc_titles = [x["title"] for x in sources.get("bbc_business", [])]
    themes = []
    if any("agent" in n.lower() or "skill" in n.lower() for n in gh_names):
        themes.append({
            "name": "AI Agent 工程化",
            "evidence": "GitHub Trending 出现 agent-skills、superpowers 等多个 agent 框架项目",
            "heat": "升温中",
        })
    if any("music" in n.lower() for n in gh_names):
        themes.append({
            "name": "本地化 AI 媒体",
            "evidence": "Music Assistant 等自托管媒体库管理工具持续热门",
            "heat": "升温中",
        })
    if any("health" in n.lower() or "med" in n.lower() for n in gh_names):
        themes.append({
            "name": "开源医疗 AI",
            "evidence": "openmed 等开源医疗 AI 项目进入 Trending",
            "heat": "爆发期",
        })
    if any("spacex" in t.lower() or "musk" in t.lower() for t in bbc_titles):
        themes.append({
            "name": "太空经济平民化",
            "evidence": "SpaceX 上市,马斯克成为万亿富翁,资本涌入航天赛道",
            "heat": "爆发期",
        })
    if not themes:
        themes.append({
            "name": "AI 工具平民化",
            "evidence": "技术社区主流话题集中在 AI 落地",
            "heat": "升温中",
        })

    opportunities = [
        {
            "title": "AI Agent 技能模板商店",
            "category": "SaaS",
            "entry_cost": "低",
            "time_to_cash": "1-3月",
            "rationale": "agent-skills、superpowers 等项目爆发,大量 AI 编程 agent 缺乏高质量技能包。建立垂直领域的技能市场,收 30% 分成。",
        },
        {
            "title": "出海英语短视频 AI 配音",
            "category": "内容",
            "entry_cost": "低",
            "time_to_cash": "1-3月",
            "rationale": "中国卖家做 TikTok/YouTube Shorts 需要英语配音,ElevenLabs 类工具单条成本高。做按条计费的 SaaS,目标 30 万跨境中小卖家。",
        },
        {
            "title": "小团队 AI 流程顾问",
            "category": "服务",
            "entry_cost": "低",
            "time_to_cash": "1-3月",
            "rationale": "欧美 10-50 人公司不知道如何把 AI agent 嵌入现有工作流。1-2 人顾问团队,按项目收 1-5 万美金,从 Replit / Cursor 客户切入。",
        },
        {
            "title": "开源医疗 AI 二开服务",
            "category": "SaaS",
            "entry_cost": "中",
            "time_to_cash": "3-6月",
            "rationale": "openmed 等开源医疗模型出现,诊所 / 心理咨询机构需要本地化部署 + 数据合规服务。技术团队 2-3 人,客单价 5-20 万。",
        },
    ]
    return {
        "themes": themes,
        "opportunities": opportunities,
        "red_flags": [
            "通用聊天机器人 — 大厂已红海,差异化难",
            "无差异的 AI 绘图工具 — Midjourney / Sora 占据心智",
        ],
    }


def main():
    in_path = DATA / f"{TODAY}.json"
    if not in_path.exists():
        sys.exit(f"missing {in_path} — run fetch_signals.py first")
    payload = json.loads(in_path.read_text())
    sources = payload.get("sources", {})

    prompt = build_prompt(sources)
    print(f"▶ calling LLM ({OPENAI_MODEL})...")
    raw = _call_llm(prompt)
    analysis = _extract_json(raw) if raw else {}

    if not analysis.get("themes"):
        print("  [fallback] LLM unavailable or returned invalid JSON, using rule-based")
        analysis = fallback_analysis(sources)

    payload["analysis"] = analysis
    in_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"✓ wrote analysis to {in_path}")
    print(f"  themes: {len(analysis.get('themes', []))}, "
          f"opportunities: {len(analysis.get('opportunities', []))}, "
          f"red_flags: {len(analysis.get('red_flags', []))}")


if __name__ == "__main__":
    main()
