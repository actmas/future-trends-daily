#!/usr/bin/env python3
"""
Worktree-pattern publish to gh-pages branch. Reads GH_OWNER and TRENDS_REPO
from ~/.hermes/.env, pushes site/ to the gh-pages branch.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
SITE = PROJECT / "site"
WORKTREE = PROJECT / ".gh-pages-wt"

BJ = timezone(timedelta(hours=8))
TODAY = datetime.now(BJ).strftime("%Y-%m-%d")

ENV_FILE = Path.home() / ".hermes" / ".env"
_env_text = ENV_FILE.read_text() if ENV_FILE.exists() else ""


def _envval(key: str, default: str | None = None) -> str | None:
    m = re.search(rf"^{key}=(.*)$", _env_text, re.M)
    return m.group(1).strip().strip('"').strip("'") if m else default


OWNER = _envval("GH_OWNER")
REPO = _envval("TRENDS_REPO") or _envval("GH_REPO")
if not OWNER or not REPO:
    sys.exit("GH_OWNER / TRENDS_REPO not set in ~/.hermes/.env")
TOKEN = _envval("GITHUB_TOKEN")
if not TOKEN:
    sys.exit("GITHUB_TOKEN not set in ~/.hermes/.env")


def _run(cmd: list[str], cwd: Path | None = None, check: bool = True):
    print(f"  $ {' '.join(cmd[:6])}", file=sys.stderr)
    res = subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=check,
                         capture_output=True, text=True)
    if res.returncode != 0 and check:
        print(res.stdout, file=sys.stderr)
        print(res.stderr, file=sys.stderr)
    return res


def ensure_repo():
    """Create the repo if it doesn't exist (idempotent)."""
    import urllib.request, urllib.error
    body = f'{{"name":"{REPO}","description":"未来风口雷达 — 每日 12:00 自动生成","private":false,"auto_init":true}}'
    req = urllib.request.Request(
        "https://api.github.com/user/repos",
        data=body.encode(),
        method="POST",
        headers={
            "Authorization": f"token {TOKEN}",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            print(f"  ✓ repo created: {r.status}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        if e.code == 422 and "name already exists" in body:
            print("  · repo already exists")
        elif e.code == 401:
            print(f"  ✗ 401 — token invalid. Set GITHUB_TOKEN in ~/.hermes/.env")
            sys.exit(1)
        else:
            print(f"  ? repo create HTTP {e.code}: {body[:200]}")
            sys.exit(1)


def ensure_pages():
    """Enable Pages on gh-pages branch."""
    import urllib.request, urllib.error
    req = urllib.request.Request(
        f"https://api.github.com/repos/{OWNER}/{REPO}/pages",
        data=b'{"source":{"branch":"gh-pages","path":"/"}}',
        method="POST",
        headers={
            "Authorization": f"token {TOKEN}",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            print(f"  ✓ pages enabled: {r.status}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        if e.code in (409, 422):
            print(f"  · pages already configured ({e.code})")
        else:
            print(f"  ? pages HTTP {e.code}: {body[:200]}")


def publish():
    # 1. Ensure clean state
    if not (PROJECT / ".git").exists():
        _run(["git", "init", "-b", "main"], cwd=PROJECT)
        _run(["git", "config", "user.name", "future-trends-bot"], cwd=PROJECT)
        _run(["git", "config", "user.email", "bot@hermes.local"], cwd=PROJECT)
        _run(["git", "add", "-A"], cwd=PROJECT)
        _run(["git", "commit", "-m", "chore: initial source"], cwd=PROJECT)
        remote = f"https://x-access-token:{TOKEN}@github.com/{OWNER}/{REPO}.git"
        _run(["git", "remote", "add", "origin", remote], cwd=PROJECT, check=False)
        _run(["git", "push", "-u", "origin", "main", "--force"], cwd=PROJECT)

    remote = f"https://x-access-token:{TOKEN}@github.com/{OWNER}/{REPO}.git"
    # Make sure remote is set with current token
    _run(["git", "remote", "set-url", "origin", remote], cwd=PROJECT, check=False)

    # 2. Clean worktree
    _run(["git", "worktree", "prune"], cwd=PROJECT, check=False)
    if WORKTREE.exists():
        _run(["git", "worktree", "remove", "--force", str(WORKTREE)],
             cwd=PROJECT, check=False)
    _run(["git", "branch", "-D", "gh-pages"], cwd=PROJECT, check=False)

    # 3. Create fresh worktree on gh-pages
    _run(["git", "fetch", "origin"], cwd=PROJECT, check=False)
    _run(["git", "worktree", "add", "-b", "gh-pages",
         str(WORKTREE), "origin/main"], cwd=PROJECT, check=True)
    _run(["git", "checkout", "gh-pages"], cwd=PROJECT, check=False)
    # back in main worktree, worktree is at WORKTREE
    # Now populate worktree
    if (WORKTREE).exists():
        for item in WORKTREE.iterdir():
            if item.name == ".git":
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    shutil.copytree(SITE, WORKTREE, dirs_exist_ok=True)
    (WORKTREE / ".nojekyll").write_text("")
    _run(["git", "add", "-A"], cwd=WORKTREE)
    status = _run(["git", "status", "--porcelain"], cwd=WORKTREE, check=True)
    if not status.stdout.strip():
        print("  · no changes to publish")
    else:
        _run(["git", "commit", "-m", f"publish: {TODAY}"], cwd=WORKTREE, check=True)
    _run(["git", "push", "origin", "gh-pages", "--force"], cwd=WORKTREE, check=True)


def verify():
    """Verify the blob is in the gh-pages tree (not just that a commit was pushed)."""
    res = _run(["git", "ls-tree", "origin/gh-pages", "reports/"],
               cwd=PROJECT, check=False)
    found = TODAY in res.stdout
    if found:
        print(f"  ✓ {TODAY}.html confirmed in gh-pages tree")
    else:
        print(f"  ✗ {TODAY}.html NOT in gh-pages tree — publish race?")
    return found


def main():
    print(f"▶ publishing {OWNER}/{REPO}...")
    ensure_repo()
    publish()
    ensure_pages()
    ok = verify()
    if ok:
        print(f"\nhttps://{OWNER}.github.io/{REPO}/")


if __name__ == "__main__":
    main()
