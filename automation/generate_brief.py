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
import random
import datetime as dt
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "automation"
BRIEFS = ROOT / "briefs"
TOPICS_JSON = DATA / "topics.json"
UNIVERSE_JSON = DATA / "universe.json"
FORMAT = os.environ.get("FORMAT", "battle")   # battle | comic (Toolverse) | news (daily AI news)

MODEL = os.environ.get("BLOG_MODEL", "openai/gpt-4o-mini")
ENDPOINT = os.environ.get("MODELS_ENDPOINT", "https://models.github.ai/inference/chat/completions")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("MODELS_TOKEN")
# Provider chain: Gemini free tier -> Claude -> free GitHub Models.
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")
GEMINI_KEYS = [k for k in (os.environ.get("GEMINI_API_KEY"),
                           os.environ.get("GEMINI_API_KEY_2")) if k]
GEMINI_KEY = GEMINI_KEYS[0] if GEMINI_KEYS else None
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
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


def _gemini_completion(user, max_tokens):
    last = ""
    for attempt in range(3 * max(1, len(GEMINI_KEYS))):
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
                params={"key": GEMINI_KEYS[attempt % len(GEMINI_KEYS)]},
                json={
                    "systemInstruction": {"parts": [{"text": SYSTEM}]},
                    "contents": [{"role": "user", "parts": [{"text": user}]}],
                    # thinkingBudget 0: 2.5-flash otherwise spends thinking tokens
                    # from maxOutputTokens and can truncate the JSON mid-object
                    # (suspected cause of the 2026-07-05 news-slot failure).
                    "generationConfig": {"temperature": 0.9, "maxOutputTokens": max_tokens,
                                         "responseMimeType": "application/json",
                                         "thinkingConfig": {"thinkingBudget": 0}},
                },
                timeout=120,
            )
        except requests.RequestException as e:
            last = str(e); time.sleep(2 * (attempt + 1)); continue
        if r.status_code < 400:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        last = f"{r.status_code}: {r.text[:200]}"
        if r.status_code in (429, 500, 502, 503):
            time.sleep(4 * (attempt + 1)); continue
        break
    raise RuntimeError(f"gemini failed ({last})")


def _raw_completion(user, max_tokens):
    if GEMINI_KEY:
        try:
            return _gemini_completion(user, max_tokens)
        except Exception as e:
            print(f"gemini unavailable ({e}); trying next provider", file=sys.stderr)
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


def _extract_first_json_block(text):
    """First balanced {...} block, or None. Handles fenced or prose-wrapped
    model output that plain json.loads rejects. Truncated output (a brace
    that never closes) returns None instead of raising."""
    text = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text)
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def chat_json(user, max_tokens=3000):
    content = _raw_completion(user, max_tokens)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        json_text = _extract_first_json_block(content)
        if json_text is None:
            sys.exit(f"model did not return JSON: {content[:300]}")
        try:
            return json.loads(json_text)
        except json.JSONDecodeError as e:
            sys.exit(f"model JSON unparseable ({e}): {json_text[:300]}")


# Hook styles rotate deterministically across briefs so ~30 videos give a
# comparable sample per style; analytics_report.py joins hook_type back to
# retention so the winning opener can be doubled down on.
HOOK_STYLES = {
    "question": "a sharp QUESTION the viewer needs answered "
                "(e.g. 'Which AI actually writes better ads?')",
    "bold_claim": "a surprising BOLD CLAIM stated flat as fact "
                  "(e.g. 'One of these tools is a waste of money.')",
    "result_first": "the RESULT teased up front without the reasoning "
                    "(e.g. 'The winner shocked me, and it was not ChatGPT.')",
    "conflict_tease": "pure CONFLICT and stakes, movie-trailer style "
                      "(e.g. 'Two AI giants walk in. One limps out.')",
    "pain_point": "the viewer's PAIN named in one line "
                  "(e.g. 'Still paying for the wrong AI writer?')",
}


def pick_hook_style():
    """Rotate through HOOK_STYLES by brief count: even coverage, reproducible."""
    order = sorted(HOOK_STYLES)
    n = len(list(BRIEFS.glob("*.json"))) if BRIEFS.exists() else 0
    return order[n % len(order)]


CLASSIC_BULLETS = (
    "- narration: an array of 9-14 segments. Each segment is an object with "
    '"text" (ONE short spoken sentence, max 14 words, punchy and fast-paced; no filler, '
    'no throat-clearing) and "broll" (a 2-4 word stock-footage search query '
    "that matches the text, e.g. 'person typing laptop', 'data center servers'). The first "
    "segment's text must start with the hook. The FINAL segment must be a short, natural "
    "call-to-action: ask one quick question inviting a comment, then a brief nudge to follow "
    "for daily AI tools. Never the generic 'like, comment, share and subscribe' line.\n"
)

BATTLE_BULLETS = (
    "- battle: REQUIRED (this topic is an X vs Y battle): "
    '{"toolA": "Name", "toolB": "Name", "tagline": "a question of 8 words or fewer for the '
    'intro card", "rounds": [2 or 3 items of {"title": "1-3 words, e.g. Price", '
    '"aPoint": "toolA in this round, 9 words or fewer", "bPoint": "same for toolB", '
    '"winner": "a" or "b"}], "verdict": "28 words or fewer naming the overall winner and '
    'what the loser is still better for"}.\n'
    "- narration: an array of EXACTLY rounds+2 segments (3 rounds -> 5 segments; 2 rounds -> 4). "
    'Each segment is an object with "text" and "broll" (a 2-4 word stock-footage search query). '
    "The segments map 1:1 onto the video scenes: segment 1 = the hook plus a one-line setup of "
    "the matchup (plays over the VS intro card); then ONE segment per round (say what the round "
    "tests, compare both tools concretely, declare the round winner; 2 or 3 short sentences, "
    "max 35 words); final segment = the verdict spoken naturally, then ask viewers which tool "
    "they would pick in the comments and nudge them to follow for daily AI battles. Spoken "
    'round winners MUST match the "winner" fields and the spoken verdict MUST match "verdict". '
    "Do not add extra segments. WRITE THE NARRATION LIKE AN EXCITED SPORTS COMMENTATOR CALLING "
    "A MATCH: high energy, short punchy sentences, exclamation marks where natural, a rhetorical "
    "question or two, real reactions ('Ouch.', 'That one hurts.', 'No contest here!'). It must "
    "sound spoken, never like an article being read aloud.\n"
)


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


def generate_brief(topic, hook_style):
    b = _generate_once(topic, hook_style)
    if " vs " in topic.lower() and not b.get("battle"):
        print("battle block missing/invalid; retrying with a stern reminder", file=sys.stderr)
        stern = (
            "\n\nYOUR PREVIOUS ATTEMPT FAILED validation: it was missing a valid "
            '"battle" object, or the narration did not have exactly rounds+2 '
            "segments. This topic IS an X vs Y battle. Return the battle object "
            "AND exactly rounds+2 narration segments (one for the intro, one per "
            "round, one for the verdict). Count the segments before answering."
        )
        b2 = _generate_once(topic, hook_style, extra=stern)
        if b2.get("battle"):
            b = b2
    return b


def _generate_once(topic, hook_style, extra=""):
    is_battle = " vs " in topic.lower()
    user = (
        f'Write the script and metadata for a 60-90 second faceless YouTube video on: "{topic}".\n\n'
        "Return a single JSON object with these keys:\n"
        "- slug: kebab-case, 3-6 words, no dates\n"
        "- title: a clear, honest, clickable YouTube title, <=70 chars, no clickbait lies\n"
        "- hook: the spoken opening line (<=14 words). It must be a scroll-stopping "
        f"pattern-interrupt of this exact style: {HOOK_STYLES[hook_style]}. "
        "No generic intros like 'In this video'.\n"
        + (BATTLE_BULLETS if is_battle else CLASSIC_BULLETS) +
        "- description: a YouTube description, 2 or 3 sentences. Do NOT list links here.\n"
        "- links: an array of the tools/resources you mention, each an object "
        '{"name": "Tool Name", "url": "https://official-homepage"} using the real official website. '
        "3 to 8 items. Only include tools you actually name in the narration.\n"
        "- tags: an array of 8-12 lowercase search tags (do not include any year)\n"
        "- thumbnail_text: 3-5 punchy words for the thumbnail\n"
        "Keep claims general and accurate. No em dashes anywhere."
        + extra
    )
    b = _clean_common(chat_json(user))
    battle = _clean_battle(b.get("battle"), b["narration"])
    if battle:
        b["battle"] = battle
    else:
        b.pop("battle", None)
    return b


def _clean_comic(cm, narration, uni):
    """Validate the comic block against the universe bible. None = drop
    (render then falls back to the b-roll format, narration still works)."""
    if not isinstance(cm, dict):
        return None
    try:
        by_name = {h["tool"].lower(): h for h in uni["heroes"]}
        heroes = []
        for h in cm.get("heroes") or []:
            base = by_name.get(str(h.get("tool", "")).strip().lower())
            if not base:
                raise ValueError(f"unknown hero {h.get('tool')!r}")
            heroes.append({"tool": base["tool"], "alias": base["alias"],
                           "color": base["color"],
                           "power": strip_em(str(h.get("powerLine") or base["power"])).strip()})
        if not 1 <= len(heroes) <= 2:
            raise ValueError(f"{len(heroes)} heroes")
        if len(narration) != len(heroes) + 2:
            raise ValueError(f"narration {len(narration)} segs != heroes+2")
        threat = strip_em(str(cm["threat"])).strip()
        res = strip_em(str(cm["resolution"])).strip()
        if not threat or not res:
            raise ValueError("empty field")
        return {"threat": threat, "heroes": heroes, "resolution": res}
    except (KeyError, ValueError, TypeError) as e:
        print(f"comic block dropped ({e}); render falls back to b-roll", file=sys.stderr)
        return None


def _clean_common(b):
    """Shared brief cleaning: required keys, narration, links, tags, slug."""
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
                          "broll": strip_em(str(seg.get("broll", b["title"]))).strip()})
    b["narration"] = clean
    b["tags"] = [strip_em(str(t)).strip().lower() for t in b.get("tags", []) if str(t).strip()]
    links = []
    for it in (b.get("links") or []):
        if isinstance(it, dict) and it.get("name") and str(it.get("url", "")).startswith("http"):
            links.append({"name": strip_em(str(it["name"])).strip(), "url": str(it["url"]).strip()})
    b["links"] = links
    b["slug"] = re.sub(r"[^a-z0-9-]", "", b["slug"].lower().replace(" ", "-")).strip("-")
    if not b["slug"] or not b["narration"]:
        sys.exit("brief unusable after cleaning")
    return b


def generate_comic_brief(villain, uni, hook_style):
    heroes_txt = "\n".join(f"- {h['tool']} ({h['alias']}): {h['power']}" for h in uni["heroes"])
    user = (
        'Write one episode of "The AI Toolverse", a superhero comic told as a 60-90 second '
        f"faceless YouTube Short. Universe: {uni['universe']}\n"
        f"Tonight's villain: {villain['name']}: {villain['menace']}.\n"
        f"The heroes are real AI tools; their powers are their REAL features:\n{heroes_txt}\n\n"
        "Return a single JSON object with these keys:\n"
        "- slug: kebab-case, 3-6 words\n"
        "- title: episode-style, <=70 chars (e.g. 'The Blank Page strikes. Two heroes answer.')\n"
        "- hook: <=14 words, a dramatic opener in this exact style: "
        f"{HOOK_STYLES[hook_style]}\n"
        '- comic: {"threat": "the villain name", "heroes": [1 or 2 of {"tool": "EXACT tool name '
        'from the list", "powerLine": "<=10 words: the move they use, grounded in the real '
        'feature"}], "resolution": "<=25 words: how the day was saved and why that tool"}\n'
        "- narration: EXACTLY heroes+2 segments, each {\"text\", \"broll\" (2-4 word stock query)}. "
        "Segment 1 = NARRATOR: the threat strikes, a REAL relatable creator scenario told like a "
        "movie trailer (2-3 short sentences). One segment per hero = THE HERO SPEAKS, first person, "
        "fully in character (each hero has its own voice actor): announce themselves by alias, name "
        "their real tool, and describe the move they use on the threat, concrete and accurate "
        "(e.g. 'I am Scribe. Watch: Writesonic floods this empty page with copy before the Dragon "
        "can blink.'). Final segment = NARRATOR: victory, one practical takeaway, then ask which "
        "hero viewers want in the next episode and a follow nudge. Max 35 words per segment. Epic "
        "anime-trailer energy, spoken and punchy, never flat.\n"
        "- description: 2-3 sentences. No links in it.\n"
        '- links: the hero tools only, [{"name", "url": official homepage}]\n'
        "- tags: 8-12 lowercase search tags\n"
        "- thumbnail_text: 3-5 punchy words\n"
        "Accurate about what the tools actually do. No em dashes anywhere."
    )
    b = _clean_common(chat_json(user))
    comic = _clean_comic(b.get("comic"), b["narration"], uni)
    if not comic:
        b2 = _clean_common(chat_json(
            user + "\n\nYOUR PREVIOUS ATTEMPT FAILED validation: the comic object was missing/"
            "invalid, a hero was not an EXACT tool name from the list, or narration was not "
            "exactly heroes+2 segments. Fix all of that. Count the segments before answering."))
        comic = _clean_comic(b2.get("comic"), b2["narration"], uni)
        if comic:
            b = b2
    if comic:
        b["comic"] = comic
    else:
        b.pop("comic", None)
    return b


NEWS_CATEGORIES = ("chips", "models", "apps", "money", "policy", "research")


def _clean_news(nw, narration):
    """Validate the news block. None = unusable (caller aborts: a news video
    with hallucinated stories must never ship)."""
    if not isinstance(nw, dict):
        return None
    try:
        stories = []
        for s in nw.get("stories") or []:
            cat = str(s.get("category", "")).strip().lower()
            if cat not in NEWS_CATEGORIES:
                cat = "apps"
            stories.append({"title": strip_em(str(s["title"])).strip(),
                            "source": strip_em(str(s["source"])).strip(),
                            "category": cat,
                            "detail": strip_em(str(s["detail"])).strip()})
        if not 3 <= len(stories) <= 5:
            raise ValueError(f"{len(stories)} stories")
        if len(narration) != len(stories) + 2:
            raise ValueError(f"narration {len(narration)} segs != stories+2")
        out = {"headline": strip_em(str(nw["headline"])).strip(),
               "outro": strip_em(str(nw["outro"])).strip(),
               "stories": stories}
        if not out["headline"] or not out["outro"]:
            raise ValueError("empty field")
        if any(not (s["title"] and s["source"] and s["detail"]) for s in stories):
            raise ValueError("empty story field")
        return out
    except (KeyError, ValueError, TypeError) as e:
        print(f"news block invalid ({e})", file=sys.stderr)
        return None


def generate_news_brief(stories, hook_style):
    """Script today's AI-news Short, grounded ONLY in the fetched stories."""
    lines = []
    for i, s in enumerate(stories, 1):
        lines.append(f"{i}. [{s['category']}] {s['title']} (sources: {', '.join(s['sources'])})\n"
                     f"   {s['summary'][:320]}")
    feed = "\n".join(lines)
    user = (
        "Script a 60-90 second faceless 'Daily AI News' YouTube Short from TODAY'S real "
        "stories below. Pick the 4 most impactful, varied stories (avoid two takes on the "
        "same theme; prefer different categories).\n\n"
        f"TODAY'S STORIES (your ONLY permitted facts):\n{feed}\n\n"
        "CRITICAL GROUNDING RULE: every claim in the narration and every story field must "
        "come from the summaries above. Do NOT add numbers, product names, dates or details "
        "that are not in them. If a summary is thin, stay general. Attribute each story to "
        "its source by name in the narration (e.g. 'TechCrunch reports').\n\n"
        "Return a single JSON object with these keys:\n"
        "- slug: kebab-case, 3-6 words, no dates\n"
        "- title: a clickable YouTube title for today's AI news roundup, <=70 chars, "
        "name the single biggest story in it\n"
        "- hook: the spoken opening line (<=14 words), a scroll-stopping pattern-interrupt "
        f"of this exact style: {HOOK_STYLES[hook_style]}\n"
        '- news: {"headline": "the day\'s biggest angle for the intro card, <=12 words", '
        '"stories": [EXACTLY the 4 chosen, in the order you cover them, each '
        '{"title": "display headline <=9 words", "source": "the outlet name", '
        '"category": "one of chips|models|apps|money|policy|research", '
        '"detail": "one concrete display line from the summary: a complete capitalised '
        'sentence <=14 words, readable on its own"}], '
        '"outro": "a follow call-to-action <=12 words"}\n'
        "- narration: EXACTLY stories+2 segments, each {\"text\", \"broll\" (2-4 word stock "
        "query)}. Segment 1 = the hook plus a one-line tease of the biggest story (plays over "
        "the intro card). Then ONE segment per story in the same order as news.stories: what "
        "happened, why it matters, source named; 2-3 short sentences, max 32 words. Final "
        "segment = quick sign-off, ask viewers which story matters most to them in the "
        "comments, and nudge a follow for tomorrow's brief. READ LIKE AN ENERGETIC NEWS "
        "ANCHOR: urgent, crisp, confident. Short punchy sentences. It must sound spoken.\n"
        "- description: 2-3 sentences summarising today's brief. No links.\n"
        '- links: [] (news videos have no tool links)\n'
        "- tags: 8-12 lowercase search tags (do not include any year)\n"
        "- thumbnail_text: 3-5 punchy words\n"
        "No em dashes anywhere."
    )
    b = _clean_common(chat_json(user, max_tokens=4000))
    news = _clean_news(b.get("news"), b["narration"])
    if not news:
        b = _clean_common(chat_json(
            user + "\n\nYOUR PREVIOUS ATTEMPT FAILED validation: the news object was "
            "missing/invalid or narration was not exactly stories+2 segments. Return "
            "3-5 stories and count the narration segments before answering.",
            max_tokens=4000))
        news = _clean_news(b.get("news"), b["narration"])
    if not news:
        sys.exit("news brief failed validation twice; not risking a hallucinated news video")
    b["news"] = news
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
    hook_style = os.environ.get("HOOK_STYLE") or pick_hook_style()
    if hook_style not in HOOK_STYLES:
        sys.exit(f"unknown HOOK_STYLE {hook_style!r}; options: {', '.join(sorted(HOOK_STYLES))}")
    print(f"Hook style: {hook_style}")
    if FORMAT == "news":
        from news_sources import fetch_news
        print("Fetching today's AI news...")
        stories = fetch_news(limit=8)
        if len(stories) < 3:
            sys.exit(f"only {len(stories)} fresh AI stories found; not enough for a news video")
        for s in stories:
            print(f"  [{s['category']}] {s['title']}  ({', '.join(s['sources'])})")
        topic = "Daily AI news"
        brief = generate_news_brief(stories, hook_style)
        today_d = dt.datetime.now(dt.timezone.utc).date()
        brief["news"]["dateLabel"] = f"{today_d.day} {today_d.strftime('%B %Y')}"
        brief["slug"] = f"ai-news-{today_d.strftime('%Y%m%d')}"
    elif FORMAT == "comic" and UNIVERSE_JSON.exists():
        uni = load(UNIVERSE_JSON)
        used = set(uni.get("published_threats", []))
        pool = [v for v in uni["villains"] if v["name"] not in used]
        if not pool:                                   # season over: start again
            uni["published_threats"], pool = [], list(uni["villains"])
        villain = random.choice(pool)
        topic = f"Toolverse episode: {villain['name']}"
        print(f"Generating comic episode: {villain['name']}")
        brief = generate_comic_brief(villain, uni, hook_style)
        uni.setdefault("published_threats", []).append(villain["name"])
        save(UNIVERSE_JSON, uni)
    else:
        topics = load(TOPICS_JSON)
        if not topics["queue"]:
            replenish(topics, want=12)
            if not topics["queue"]:
                sys.exit("no topics available and replenish failed")
        topic = topics["queue"].pop(0)
        print(f"Generating brief for: {topic}")
        brief = generate_brief(topic, hook_style)
        topics["published"].append(topic)
        if len(topics["queue"]) < 5:
            replenish(topics)
        save(TOPICS_JSON, topics)

    today = os.environ.get("POST_DATE") or dt.datetime.now(dt.timezone.utc).date().isoformat()
    brief["topic"] = topic
    brief["date"] = today
    brief["hook_type"] = hook_style

    BRIEFS.mkdir(exist_ok=True)
    out = BRIEFS / f"{brief['slug']}.json"
    if out.exists():
        # Recycled villains / rematch topics can regenerate an old slug;
        # overwriting would clobber the old brief analytics joins against.
        brief["slug"] += "-" + today.replace("-", "")[4:]
        out = BRIEFS / f"{brief['slug']}.json"
        n = 2
        while out.exists():          # date suffix can still collide (2nd news
            out = BRIEFS / f"{brief['slug']}-{n}.json"   # brief the same day)
            n += 1
        brief["slug"] = out.stem
    save(out, brief)
    (DATA / "latest.txt").write_text(brief["slug"], encoding="utf-8")   # render uses this

    secs = sum(max(2, len(s["text"].split()) / 2.6) for s in brief["narration"])
    print(f"Wrote {out.relative_to(ROOT)}  ({len(brief['narration'])} segments, ~{int(secs)}s)")
    print(f"Title: {brief['title']}")


if __name__ == "__main__":
    main()
