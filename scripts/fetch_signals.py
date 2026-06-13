#!/usr/bin/env python3
"""
Fetch raw signals from multiple dimensions:
  1. International e-commerce hot search (Amazon / eBay / Etsy bestsellers)
  2. International development news (Reuters / Bloomberg / FT headlines)
  3. Social-media discussion trends (Reddit / X / Hacker News)
  4. Chinese outbound demand (smzdm / 知乎 / 小红书 blocked — skip per hard rules)
  5. GitHub trending tech stacks (already in gh-trending-daily — pull recent)

Each source is a best-effort fetch with hard timeouts. Failed sources produce
empty arrays, never crash the whole pipeline. Output: data/<date>.json.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
DATA = PROJECT / "data"
DATA.mkdir(exist_ok=True)

BJ = timezone(timedelta(hours=8))
TODAY = datetime.now(BJ).strftime("%Y-%m-%d")
TIMESTAMP = datetime.now(BJ).strftime("%Y-%m-%d %H:%M:%S 北京时间")

# Known hard-blocked on this host (per memory). Don't retry.
HARD_BLOCKED_DOMAINS = {
    "amazon.com": "amazon bestsellers SSR data unavailable",
    "x.com": "login required",
    "twitter.com": "login required",
    "xiaohongshu.com": "login required",
    "smzdm.com": "探测脚本拦截",
    "baidu.com": "安全验证",
    "google.com": "redirect/search not accessible",
}

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def _http_get(url: str, timeout: int = 15) -> str | None:
    """Best-effort GET. Returns body or None on any failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [skip] {url[:60]}... : {type(e).__name__}", file=sys.stderr)
        return None


def fetch_reddit_top() -> list[dict]:
    """Top posts from r/technology, r/Futurology, r/entrepreneur, r/startups,
    r/sidehustle, r/ecommerce, r/investing — 24h window. Public JSON endpoint,
    no auth."""
    subs = ["Futurology", "entrepreneur", "startups", "sidehustle",
            "ecommerce", "investing", "personalfinance", "technology"]
    items: list[dict] = []
    for s in subs:
        url = f"https://www.reddit.com/r/{s}/top.json?t=day&limit=8"
        body = _http_get(url, timeout=12)
        if not body:
            continue
        try:
            d = json.loads(body)
            for ch in d.get("data", {}).get("children", []):
                pd = ch.get("data", {})
                items.append({
                    "sub": s,
                    "title": pd.get("title", ""),
                    "score": pd.get("score", 0),
                    "comments": pd.get("num_comments", 0),
                    "url": "https://reddit.com" + pd.get("permalink", ""),
                    "domain": pd.get("domain", ""),
                })
        except Exception:
            continue
    items.sort(key=lambda x: x.get("score", 0), reverse=True)
    return items[:30]


def fetch_hackernews_top() -> list[dict]:
    """Top HN stories via official Firebase API."""
    ids_body = _http_get("https://hacker-news.firebaseio.com/topstories.json", timeout=10)
    if not ids_body:
        return []
    try:
        ids = json.loads(ids_body)[:25]
    except Exception:
        return []
    items: list[dict] = []
    for hid in ids:
        body = _http_get(f"https://hacker-news.firebaseio.com/item/{hid}.json", timeout=8)
        if not body:
            continue
        try:
            d = json.loads(body)
            if d and d.get("type") == "story" and d.get("title"):
                items.append({
                    "title": d.get("title", ""),
                    "score": d.get("score", 0),
                    "comments": d.get("descendants", 0),
                    "url": d.get("url") or f"https://news.ycombinator.com/item?id={hid}",
                    "source": "hn",
                })
        except Exception:
            continue
    return items[:20]


def fetch_reuters_world() -> list[dict]:
    """Reuters world RSS — public endpoint, no auth."""
    body = _http_get("https://feeds.reuters.com/Reuters/worldNews", timeout=12)
    if not body:
        return []
    items: list[dict] = []
    for m in re.finditer(r"<item>(.*?)</item>", body, re.S):
        block = m.group(1)
        title = re.search(r"<title>(.*?)</title>", block, re.S)
        link = re.search(r"<link>(.*?)</link>", block)
        pub = re.search(r"<pubDate>(.*?)</pubDate>", block)
        if title and link:
            items.append({
                "title": re.sub(r"<!\[CDATA\[|\]\]>", "", title.group(1)).strip(),
                "url": link.group(1).strip(),
                "published": (pub.group(1).strip() if pub else ""),
                "source": "reuters",
            })
    return items[:25]


def fetch_bbc_business() -> list[dict]:
    """BBC Business RSS — public."""
    body = _http_get("https://feeds.bbci.co.uk/news/business/rss.xml", timeout=12)
    if not body:
        return []
    items: list[dict] = []
    for m in re.finditer(r"<item>(.*?)</item>", body, re.S):
        block = m.group(1)
        title = re.search(r"<title>(.*?)</title>", block, re.S)
        link = re.search(r"<link>(.*?)</link>", block)
        if title and link:
            items.append({
                "title": re.sub(r"<!\[CDATA\[|\]\]>", "", title.group(1)).strip(),
                "url": link.group(1).strip(),
                "source": "bbc-business",
            })
    return items[:20]


def fetch_github_trending() -> list[dict]:
    """github.com/trending HTML — first 20 entries. Public, no auth."""
    body = _http_get("https://github.com/trending", timeout=15)
    if not body:
        return []
    items: list[dict] = []
    # Each repo: <h2><a href="/owner/repo">owner / repo</a></h2> + <p class="col-9">desc</p>
    for m in re.finditer(
        r'<h2[^>]*>\s*<a[^>]+href="(/[^"]+)"[^>]*>\s*(.*?)\s*</a>',
        body, re.S,
    ):
        path = m.group(1)
        name = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        name = re.sub(r"\s+", " ", name)
        # Try to grab description from the next sibling block
        # Approximate: search the next 800 chars for <p class="col-9 ...">
        start = m.end()
        chunk = body[start:start + 1200]
        desc_m = re.search(r'<p class="col-9[^"]*">(.*?)</p>', chunk, re.S)
        desc = ""
        if desc_m:
            desc = re.sub(r"<[^>]+>", "", desc_m.group(1)).strip()
        items.append({
            "name": name,
            "url": "https://github.com" + path,
            "description": desc[:300],
        })
        if len(items) >= 15:
            break
    return items


def fetch_producthunt_today() -> list[dict]:
    """Product Hunt leaderboard via public RSS."""
    body = _http_get("https://www.producthunt.com/feed", timeout=12)
    if not body:
        return []
    items: list[dict] = []
    for m in re.finditer(r"<item>(.*?)</item>", body, re.S):
        block = m.group(1)
        title = re.search(r"<title>(.*?)</title>", block, re.S)
        link = re.search(r"<link>(.*?)</link>", block)
        if title and link:
            items.append({
                "title": re.sub(r"<!\[CDATA\[|\]\]>", "", title.group(1)).strip(),
                "url": link.group(1).strip(),
                "source": "producthunt",
            })
    return items[:15]


def main():
    print(f"▶ fetching signals for {TODAY}...")
    payload: dict = {
        "date": TODAY,
        "fetched_at": TIMESTAMP,
        "sources": {
            "reddit_top": fetch_reddit_top(),
            "hackernews_top": fetch_hackernews_top(),
            "reuters_world": fetch_reuters_world(),
            "bbc_business": fetch_bbc_business(),
            "github_trending": fetch_github_trending(),
            "producthunt_today": fetch_producthunt_today(),
        },
        "blocked_sources": list(HARD_BLOCKED_DOMAINS.keys()),
    }
    out = DATA / f"{TODAY}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    counts = {k: len(v) for k, v in payload["sources"].items()}
    print(f"✓ wrote {out}")
    print(f"  counts: {counts}")


if __name__ == "__main__":
    main()
