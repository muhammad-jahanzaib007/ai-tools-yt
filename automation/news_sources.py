#!/usr/bin/env python3
"""Free AI-news aggregator for the daily news Short.

Pulls the last ~36h of AI stories from public RSS/Atom feeds plus Hacker News
(Algolia API), dedupes stories covered by several outlets, ranks by coverage +
recency, and tags each with a category. No API keys, stdlib XML parsing only.

Used by generate_brief.py (FORMAT=news); also runnable directly:
    python automation/news_sources.py
"""

import re
import sys
import time
import html
import email.utils
import datetime as dt
import xml.etree.ElementTree as ET

import requests

UA = {"User-Agent": "Mozilla/5.0 (snackbyte-news-bot)"}
WINDOW_HOURS = 36
ATOM = "{http://www.w3.org/2005/Atom}"

FEEDS = [
    ("TechCrunch", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("The Verge", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    ("VentureBeat", "https://venturebeat.com/category/ai/feed/"),
    ("Ars Technica", "https://arstechnica.com/ai/feed/"),
    ("Google News", "https://news.google.com/rss/search?q=artificial+intelligence+when:1d"
                    "&hl=en-GB&gl=GB&ceid=GB:en"),
]

CATEGORIES = [
    ("chips", ("nvidia", "chip", "chips", "gpu", "gpus", "tsmc", "semiconductor", "silicon",
               "data center", "datacenter", "data centre", "infrastructure", "compute", "amd",
               "intel", "foundry")),
    ("money", ("funding", "raises", "raised", "billion", "million", "valuation", "acquisition",
               "acquires", "ipo", "invest", "investment", "revenue", "stock", "shares")),
    ("policy", ("regulation", "regulator", "law", "lawsuit", "court", "ban", "copyright",
                "senate", "parliament", "act", "ruling", "antitrust", "privacy")),
    ("research", ("paper", "study", "research", "researchers", "breakthrough", "benchmark",
                  "scientists", "university")),
    ("models", ("gpt", "gemini", "claude", "llama", "model", "models", "llm", "chatgpt",
                "openai", "anthropic", "deepmind", "mistral", "release", "launches")),
    ("apps", ("app", "apps", "feature", "features", "update", "tool", "assistant", "agent",
              "copilot", "integration", "adoption", "enterprise", "workers", "jobs")),
]

AI_WORDS = ("ai", "artificial intelligence", "machine learning", "llm", "gpt", "chatgpt",
            "openai", "anthropic", "gemini", "claude", "deepmind", "neural", "genai",
            "generative", "copilot", "nvidia")

STOP = {"the", "a", "an", "to", "of", "in", "on", "for", "and", "is", "its", "it", "with",
        "as", "at", "by", "after", "over", "new", "how", "why", "what", "says", "amid"}


def _clean_text(s):
    s = re.sub(r"<[^>]+>", " ", html.unescape(s or ""))
    return re.sub(r"\s+", " ", s).strip()


def _parse_date(s):
    if not s:
        return None
    try:
        return email.utils.parsedate_to_datetime(s)
    except (TypeError, ValueError):
        pass
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _feed_items(source, url):
    try:
        r = requests.get(url, headers=UA, timeout=25)
        if r.status_code != 200:
            print(f"  {source}: http {r.status_code}", file=sys.stderr)
            return []
        root = ET.fromstring(r.content)
    except Exception as e:
        print(f"  {source}: {e}", file=sys.stderr)
        return []
    items = []
    for it in root.iter("item"):                                   # RSS 2.0
        items.append({
            "source": source,
            "title": _clean_text(it.findtext("title")),
            "url": (it.findtext("link") or "").strip(),
            "summary": _clean_text(it.findtext("description"))[:400],
            "published": _parse_date(it.findtext("pubDate")),
        })
    for it in root.iter(f"{ATOM}entry"):                           # Atom
        link = it.find(f"{ATOM}link")
        items.append({
            "source": source,
            "title": _clean_text(it.findtext(f"{ATOM}title")),
            "url": link.get("href", "") if link is not None else "",
            "summary": _clean_text(it.findtext(f"{ATOM}summary")
                                   or it.findtext(f"{ATOM}content"))[:400],
            "published": _parse_date(it.findtext(f"{ATOM}published")
                                     or it.findtext(f"{ATOM}updated")),
        })
    return items


def _hn_items():
    try:
        r = requests.get("https://hn.algolia.com/api/v1/search",
                         params={"query": "AI", "tags": "story", "hitsPerPage": 25,
                                 "numericFilters":
                                     f"created_at_i>{int(time.time()) - WINDOW_HOURS * 3600},"
                                     "points>80"},
                         timeout=25)
        if r.status_code != 200:
            return []
        return [{
            "source": "Hacker News",
            "title": _clean_text(h.get("title")),
            "url": h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}",
            "summary": "",
            "published": dt.datetime.fromtimestamp(h["created_at_i"], dt.timezone.utc),
        } for h in r.json().get("hits", [])]
    except Exception as e:
        print(f"  Hacker News: {e}", file=sys.stderr)
        return []


def _is_ai(item):
    text = f"{item['title']} {item['summary']}".lower()
    return any(w in text for w in AI_WORDS)


def _tokens(title):
    words = re.sub(r"[^a-z0-9 ]", " ", title.lower()).split()
    return {w for w in words if w not in STOP and len(w) > 2}


def _category(item):
    text = f"{item['title']} {item['summary']}".lower()
    best, hits = "apps", 0
    for cat, words in CATEGORIES:
        n = sum(1 for w in words if w in text)
        if n > hits:
            best, hits = cat, n
    return best


def fetch_news(limit=8):
    """Top AI stories of the last WINDOW_HOURS, deduped + ranked.
    Returns [{title, url, summary, sources, category, hours_ago}]."""
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(hours=WINDOW_HOURS)
    raw = []
    for source, url in FEEDS:
        got = _feed_items(source, url)
        print(f"  {source}: {len(got)} items", file=sys.stderr)
        raw += got
    raw += _hn_items()

    fresh = []
    for it in raw:
        if not it["title"] or not it["published"]:
            continue
        pub = it["published"]
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=dt.timezone.utc)
        if pub < cutoff or pub > now + dt.timedelta(hours=1):
            continue
        if not _is_ai(it):
            continue
        # Aggregators (Google News, HN) mostly surface fringe outlets; a story
        # only they carry is weak signal. Named tech-press feeds are the anchor.
        it["agg"] = it["source"] in ("Google News", "Hacker News")
        if it["source"] == "Google News":
            # GN titles are "Headline - Outlet": split for clean dedupe tokens
            m = re.match(r"^(.*)\s+-\s+([^-]{2,40})$", it["title"])
            if m:
                it["title"], it["source"] = m.group(1).strip(), m.group(2).strip()
        it["published"] = pub
        fresh.append(it)

    # dedupe: same story reported by several outlets (token overlap)
    clusters = []
    for it in fresh:
        toks = _tokens(it["title"])
        if not toks:
            continue
        for cl in clusters:
            inter = len(toks & cl["tokens"])
            if inter and inter / min(len(toks), len(cl["tokens"])) >= 0.5:
                cl["items"].append(it)
                cl["tokens"] |= toks
                break
        else:
            clusters.append({"tokens": set(toks), "items": [it]})

    stories = []
    for cl in clusters:
        # Prefer a direct tech-press item's phrasing over aggregator copies
        direct = [i for i in cl["items"] if not i["agg"]] or cl["items"]
        lead = max(direct, key=lambda i: len(i["summary"]))
        sources = sorted({i["source"] for i in cl["items"]})
        newest = max(i["published"] for i in cl["items"])
        hours = (now - newest).total_seconds() / 3600
        n_direct = len({i["source"] for i in cl["items"] if not i["agg"]})
        n_agg = len(cl["items"]) - sum(1 for i in cl["items"] if not i["agg"])
        stories.append({
            "title": lead["title"],
            "url": lead["url"],
            "summary": lead["summary"] or lead["title"],
            "sources": sources,
            "category": _category(lead),
            "hours_ago": round(hours, 1),
            # direct press coverage dominates; aggregator echoes add a little;
            # recency only breaks ties so a fringe 20-minute-old blog can't
            # outrank a story the whole tech press is running
            "_score": n_direct * 3.0 + min(n_agg, 3) * 0.7
                      + max(0.0, (WINDOW_HOURS - hours) / WINDOW_HOURS),
        })
    stories.sort(key=lambda s: -s["_score"])
    for s in stories:
        s.pop("_score")
    return stories[:limit]


if __name__ == "__main__":
    for i, s in enumerate(fetch_news(), 1):
        print(f"{i}. [{s['category']}] {s['title']}")
        print(f"   {', '.join(s['sources'])} · {s['hours_ago']}h ago")
        if s["summary"] and s["summary"] != s["title"]:
            print(f"   {s['summary'][:140]}")
