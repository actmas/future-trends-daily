#!/usr/bin/env bash
# End-to-end run: fetch → analyze → render → publish
# Usage: ./run.sh [--no-publish]
set -euo pipefail
cd "$(dirname "$0")"

echo "▶ [1/4] fetch signals (reddit/hn/bbc/reuters/github/ph)"
timeout 120 python3 scripts/fetch_signals.py

echo "▶ [2/4] analyze with LLM (or fallback)"
timeout 90 python3 scripts/analyze.py

echo "▶ [3/4] render html"
python3 scripts/render_html.py

if [[ "${1:-}" != "--no-publish" ]]; then
  echo "▶ [4/4] publish to github pages"
  python3 scripts/publish.py
fi

echo "✓ done"
