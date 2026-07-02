#!/usr/bin/env python3
"""
Phase 4b: niche trend research via the YouTube Data API (API key only).

Searches recent high-performing videos around the channel's battle niche,
ranks them by views-per-day, and writes automation/trends.json. The topic
replenisher in generate_brief.py feeds these titles to the model so new
matchups follow real demand instead of guesses.

Required env (repo secret):
  YT_API_KEY   - a plain API key from the same Google Cloud project
                 (APIs & Services > Credentials > Create credentials > API key;
                 restrict it to the YouTube Data API v3).

Quota: ~100 units per search x len(QUERIES) + 1 videos.list call
(<1000 units total, daily quota is 10,000).
"""

import os
import re
import sys
import json
import datetime as dt
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "automation" / "trends.json"

KEY = os.environ.get("YT_API_KEY")
API = "https://www.googleapis.com/youtube/v3"

QUERIES = [
    "AI tools comparison",
    "ChatGPT vs",
    "AI writer vs",
    "AI voice generator comparison",
    "AI video editor vs",
    "best AI tool 2026",
    "I tested AI",
]


def search(query, published_after):
    r = requests.get(f"{API}/search", params={
        "key": KEY, "q": query, "part": "snippet", "type": "video",
        "order": "viewCount", "publishedAfter": published_after,
        "maxResults": 15, "relevanceLanguage": "en",
    }, timeout=60)
    if r.status_code >= 400:
        print(f"search '{query}' failed ({r.status_code}): {r.text[:200]}", file=sys.stderr)
        return []
    return [it["id"]["videoId"] for it in r.json().get("items", [])
            if it.get("id", {}).get("videoId")]


def main():
    if not KEY:
        sys.exit("YT_API_KEY must be set")

    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)
    published_after = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

    ids = []
    for q in QUERIES:
        for vid in search(q, published_after):
            if vid not in ids:
                ids.append(vid)
    if not ids:
        sys.exit("no search results; check YT_API_KEY / quota")

    items = []
    now = dt.datetime.now(dt.timezone.utc)
    for i in range(0, len(ids), 50):
        r = requests.get(f"{API}/videos", params={
            "key": KEY, "part": "snippet,statistics",
            "id": ",".join(ids[i:i + 50]),
        }, timeout=60)
        if r.status_code >= 400:
            print(f"videos.list failed ({r.status_code}): {r.text[:200]}", file=sys.stderr)
            continue
        for v in r.json().get("items", []):
            sn, st = v["snippet"], v.get("statistics", {})
            views = int(st.get("viewCount", 0))
            published = dt.datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00"))
            days = max((now - published).total_seconds() / 86400, 1.0)
            items.append({
                "title": sn["title"],
                "channel": sn["channelTitle"],
                "publishedAt": sn["publishedAt"],
                "views": views,
                "viewsPerDay": round(views / days),
                "videoId": v["id"],
            })

    # Keep only clearly AI-related titles; search matches loosely otherwise
    # (e.g. generic "I tested ..." videos in any language).
    ai_re = re.compile(
        r"\b(ai|a\.i\.|gpt|chatgpt|gemini|claude|copilot|midjourney|llm|"
        r"artificial intelligence)\b", re.I)
    items = [it for it in items if ai_re.search(it["title"])]

    items.sort(key=lambda x: x["viewsPerDay"], reverse=True)
    top = items[:25]
    OUT.write_text(json.dumps({
        "generated": now.date().isoformat(),
        "windowDays": 30,
        "items": top,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} with {len(top)} trending videos")
    for it in top[:5]:
        print(f"  {it['viewsPerDay']}/day  {it['title'][:70]}")


if __name__ == "__main__":
    main()
