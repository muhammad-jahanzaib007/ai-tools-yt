#!/usr/bin/env python3
"""
Phase 1: content engine for a faceless AI-tools YouTube channel.

Free: uses GitHub Models via the Actions GITHUB_TOKEN (no API key, no billing).
Produces a structured "video brief" the render stage (Phase 2) consumes:
title, hook, narration segments (each with a stock b-roll search query),
description, tags, and thumbnail text.

Output: briefs/<slug>.json  (+ advances the topic queue, auto-replenishes).

Run from the repo root. Requires GITHUB_TOKEN (provided inside GitHub Actions).
Model is configurable via BLOG_MODEL (default: openai/gpt-4o-mini).
"""

import os
import re
import sys
import json
import time
import datetime as dt
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "automation"
BRIEFS = ROOT / "briefs"
TOPICS_JSON = DATA / "topics.json"

MODEL = os.environ.get("BLOG_MODEL", "openai/gpt-4o-mini")
ENDPOINT = os.environ.get("MODELS_ENDPOINT", "https://models.github.ai/inference/chat/completions")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("MODELS_TOKEN")
# If ANTHROPIC_API_KEY is set, use Claude; otherwise fall back to free GitHub Models.
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")
EM_DASH = "—"

SYSTEM = (
    "You are the writer for a faceless YouTube channel about AI tools and AI news, aimed at a "
    "general but curious audience. You are accurate and concrete: never invent product names, "
    "prices, benchmarks, or statistics; if unsure, speak in general terms. The narration must sound "
    "natural when read aloud by a text-to-speech voice: short sentences, plain words, no markdown, "
    "no emojis, no stage directions. CRITICAL: never use an em dash; use commas, colons, or full "
    "stops. Use British English. Always reply with a single valid JSON object and nothing else."
)


def strip_em(s):
    return s.replace(f" {EM_DASH} ", ", ").replace(EM_DASH, "-") if isinstance(s, str) else s


def load(p):
    return json.loads(p.read_text(encoding="utf-8"))


def save(p, obj):
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _raw_completion(user, max_tokens):
    if ANTHROPIC_KEY:
        import anthropic
        client = anthropic.Anthropic()
        # Thinking off: on Sonnet 5 adaptive thinking is on by default when the
        # field is omitted, and thinking tokens count against max_tokens, which
        # could truncate the JSON on this short structured task.
        msg = client.messages.create(
            model=CLAUDE_MODEL, max_tokens=max_tokens, system=SYSTEM,
            thinking={"type": "disabled"},
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in msg.content if b.type == "text")
    if not TOKEN:
        sys.exit("Set ANTHROPIC_API_KEY (Claude), or run in GitHub Actions (free GitHub Models).")
    last = ""
    for attempt in range(4):
        try:
            resp = requests.post(
                ENDPOINT,
                headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json",
                         "Accept": "application/json"},
                json={
                    "model": MODEL,
                    "messages": [{"role": "system", "content": SYSTEM},
                                 {"role": "user", "content": user}],
                    "temperature": 0.8,
                    "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"},
                },
                timeout=120,
            )
        except requests.RequestException as e:
            last = str(e); time.sleep(2 * (attempt + 1)); continue
        if resp.status_code < 400:
            return resp.json()["choices"][0]["message"]["content"]
        last = f"{resp.status_code}: {resp.text[:300]}"
        if resp.status_code in (429, 500, 502, 503, 504):
            time.sleep(3 * (attempt + 1)); continue
        break
    sys.exit(f"GitHub Models request failed after retries ({last})")


def chat_json(user, max_tokens=3000):
    content = _raw_completion(user, max_tokens)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", content, re.S)
        if not m:
            sys.exit(f"model did not return JSON: {content[:300]}")
        return json.loads(m.group(0))


def _clean_battle(bt, narration):
    """Validate the optional battle block. None = unusable -> b-roll fallback."""
    if not isinstance(bt, dict):
        return None
    try:
        rounds = []
        for r in bt.get("rounds") or []:
            w = str(r.get("winner", "")).strip().lower()
            if w not in ("a", "b"):
                raise ValueError("bad winner")
            rounds.append({"title": strip_em(str(r["title"])).strip(),
                           "aPoint": strip_em(str(r["aPoint"])).strip(),
                           "bPoint": strip_em(str(r["bPoint"])).strip(),
                           "winner": w})
        if not 2 <= len(rounds) <= 3:
            raise ValueError(f"{len(rounds)} rounds")
        if len(narration) != len(rounds) + 2:
            raise ValueError(f"narration {len(narration)} segs != rounds+2")
        out = {"toolA": strip_em(str(bt["toolA"])).strip(),
               "toolB": strip_em(str(bt["toolB"])).strip(),
               "tagline": strip_em(str(bt["tagline"])).strip(),
               "rounds": rounds,
               "verdict": strip_em(str(bt["verdict"])).strip()}
        if not all([out["toolA"], out["toolB"], out["tagline"], out["verdict"]]):
            raise ValueError("empty field")
        return out
    except (KeyError, ValueError, TypeError) as e:
        print(f"battle block dropped ({e}); render falls back to b-roll", file=sys.stderr)
        return None


def generate_brief(topic):
    user = (
        f'Write the script and metadata for a 60-90 second faceless YouTube video on: "{topic}".\n\n'
        "Return a single JSON object with these keys:\n"
        "- slug: kebab-case, 3-6 words, no dates\n"
        "- title: a clear, honest, clickable YouTube title, <=70 chars, no clickbait lies\n"
        "- hook: the spoken opening line (<=14 words). Make it a scroll-stopping pattern-interrupt: "
        "a surprising claim, a sharp question, or a bold promise. No generic intros like 'In this video'.\n"
        "- narration: an array of segments, each an object with "
        '"text" and "broll" (a 2-4 word stock-footage search query that matches the text, '
        "e.g. 'person typing laptop', 'data center servers'). For a NON-battle topic: 9-14 "
        "segments, each ONE short spoken sentence (max 14 words, punchy, no filler); the first "
        "segment's text must start with the hook, and the FINAL segment is a short natural "
        "call-to-action: one quick question inviting a comment, then a nudge to follow for "
        "daily AI tools. Never the generic 'like, comment, share and subscribe' line.\n"
        "- battle: ONLY when the topic is an 'X vs Y' comparison, also return this object: "
        '{"toolA": "Name", "toolB": "Name", "tagline": "a question of 8 words or fewer for the '
        'intro card", "rounds": [2 or 3 items of {"title": "1-3 words, e.g. Price", '
        '"aPoint": "toolA in this round, 9 words or fewer", "bPoint": "same for toolB", '
        '"winner": "a" or "b"}], "verdict": "28 words or fewer naming the overall winner and '
        'what the loser is still better for"}. For battle topics the narration must instead '
        "have EXACTLY rounds+2 segments, mirroring the on-screen scenes: segment 1 = the hook "
        "plus a one-line setup of the matchup (plays over the VS intro); one segment per round "
        "(say what the round tests, compare the two tools concretely, declare the round winner; "
        "2 or 3 short sentences, max 35 words); final segment = the verdict spoken naturally, "
        "then ask viewers which tool they would pick in the comments and nudge them to follow "
        "for daily AI battles. Spoken round winners MUST match the winner fields and the spoken "
        "verdict MUST match the verdict text.\n"
        "- description: a YouTube description, 2 or 3 sentences. Do NOT list links here.\n"
        "- links: an array of the tools/resources you mention, each an object "
        '{"name": "Tool Name", "url": "https://official-homepage"} using the real official website. '
        "3 to 8 items. Only include tools you actually name in the narration.\n"
        "- tags: an array of 8-12 lowercase search tags (do not include any year)\n"
        "- thumbnail_text: 3-5 punchy words for the thumbnail\n"
        "Keep claims general and accurate. No em dashes anywhere."
    )
    b = chat_json(user)
    for k in ("slug", "title", "hook", "description", "thumbnail_text"):
        if k not in b:
            sys.exit(f"brief missing key: {k}")
        b[k] = strip_em(str(b[k]))
    if not isinstance(b.get("narration"), list) or not b["narration"]:
        sys.exit("brief missing narration segments")
    clean = []
    for seg in b["narration"]:
        if isinstance(seg, dict) and seg.get("text"):
            clean.append({"text": strip_em(str(seg["text"])).strip(),
                          "broll": strip_em(str(seg.get("broll", topic))).strip()})
    b["narration"] = clean
    b["tags"] = [strip_em(str(t)).strip().lower() for t in b.get("tags", []) if str(t).strip()]
    links = []
    for it in (b.get("links") or []):
        if isinstance(it, dict) and it.get("name") and str(it.get("url", "")).startswith("http"):
            links.append({"name": strip_em(str(it["name"])).strip(), "url": str(it["url"]).strip()})
    b["links"] = links
    battle = _clean_battle(b.get("battle"), b["narration"])
    if battle:
        b["battle"] = battle
    else:
        b.pop("battle", None)
    b["slug"] = re.sub(r"[^a-z0-9-]", "", b["slug"].lower().replace(" ", "-")).strip("-")
    if not b["slug"] or not b["narration"]:
        sys.exit("brief unusable after cleaning")
    return b


def _trend_lines(limit=12):
    """Recent high-performing niche videos from trend_research.py, if present."""
    f = DATA / "trends.json"
    if not f.exists():
        return ""
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        items = data.get("items", [])[:limit]
        if not items:
            return ""
        rows = [f"- {it['title']} ({it['viewsPerDay']} views/day)" for it in items]
        return (
            "\nFor market signal, these videos in the niche performed best over "
            f"the last 30 days (as of {data.get('generated', 'recently')}). Use them "
            "to infer which tools and angles viewers currently care about; do NOT "
            "copy titles:\n" + "\n".join(rows) + "\n"
        )
    except Exception as e:
        print(f"trends.json ignored: {e}", file=sys.stderr)
        return ""


def replenish(topics, want=12):
    try:
        used = topics["published"] + topics["queue"]
        user = (
            f"Suggest {want} distinct, specific YouTube video ideas for a faceless channel whose "
            "format is AI tool battles: verdict-driven 'X vs Y' comparisons of AI tools, for a "
            "general audience. Every idea must be a specific 'X vs Y' matchup with a concrete "
            "angle (e.g. 'for blog posts', 'on a budget', 'for beginners'). Prefer matchups that "
            "include at least one of: Writesonic, Jasper, Pictory, Synthesia, ElevenLabs, "
            "Speechify, TubeBuddy, HeyGen, InVideo, Descript, Murf, Copy.ai, Rytr. "
            "Practical, evergreen, search-friendly titles. "
            + _trend_lines()
            + "Avoid overlapping these existing ideas:\n- " + "\n- ".join(used)
            + '\nReturn a single JSON object: {"topics": ["idea 1", ...]}. No em dashes.'
        )
        data = chat_json(user, max_tokens=1200)
        existing = {t.lower() for t in used}
        for t in data.get("topics", []):
            t = strip_em(str(t)).strip()
            if t and t.lower() not in existing:
                topics["queue"].append(t)
                existing.add(t.lower())
    except SystemExit:
        raise
    except Exception as e:
        print(f"topic replenish skipped: {e}", file=sys.stderr)


def main():
    topics = load(TOPICS_JSON)
    if not topics["queue"]:
        replenish(topics, want=12)
        if not topics["queue"]:
            sys.exit("no topics available and replenish failed")

    topic = topics["queue"].pop(0)
    print(f"Generating brief for: {topic}")
    brief = generate_brief(topic)

    today = os.environ.get("POST_DATE") or dt.datetime.now(dt.timezone.utc).date().isoformat()
    brief["topic"] = topic
    brief["date"] = today

    BRIEFS.mkdir(exist_ok=True)
    out = BRIEFS / f"{brief['slug']}.json"
    save(out, brief)
    (DATA / "latest.txt").write_text(brief["slug"], encoding="utf-8")   # render uses this

    topics["published"].append(topic)
    if len(topics["queue"]) < 5:
        replenish(topics)
    save(TOPICS_JSON, topics)

    secs = sum(max(2, len(s["text"].split()) / 2.6) for s in brief["narration"])
    print(f"Wrote {out.relative_to(ROOT)}  ({len(brief['narration'])} segments, ~{int(secs)}s)")
    print(f"Title: {brief['title']}")


if __name__ == "__main__":
    main()
