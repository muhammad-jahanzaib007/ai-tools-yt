#!/usr/bin/env python3
"""Phase B: generate the Toolverse character art via Pollinations (free Flux).

One-time batch (idempotent: existing files are skipped). For every hero in
automation/universe.json: an idle pose and an attack pose. For every villain:
a menacing pose and a defeated pose. Committed to assets/toolverse/ so
episodes reuse the same art forever = high quality, zero cost, no API key.

Pollinations serves Flux with no auth. Deterministic per file via a seed so
reruns reproduce the same character. Env: POLLINATIONS_MODEL (default flux).
"""
import base64
import json
import os
import re
import sys
import time
import zlib
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "toolverse"
UNIVERSE = ROOT / "automation" / "universe.json"
ROSTER = ROOT / "automation" / "roster.json"

MODEL = os.environ.get("POLLINATIONS_MODEL") or "flux"
GEM_KEYS = [k for k in (os.environ.get("GEMINI_API_KEY"),
                        os.environ.get("GEMINI_API_KEY_2")) if k]
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")
# `or` (not the get-default) so an empty CI env var doesn't override the default
GEMINI_IMAGE_MODEL = os.environ.get("GEMINI_IMAGE_MODEL") or "gemini-3.1-flash-image"
OPENAI_IMAGE_MODEL = os.environ.get("OPENAI_IMAGE_MODEL") or "gpt-image-1"
OPENAI_IMAGE_QUALITY = os.environ.get("OPENAI_IMAGE_QUALITY") or "medium"
# Cap new generations this run (0 = no cap). Use e.g. ART_LIMIT=1 for a cheap
# single-image smoke test before committing to the whole batch.
ART_LIMIT = int(os.environ.get("ART_LIMIT") or "0")
# Only generate hero avatars (skip villains) when set.
HEROES_ONLY = (os.environ.get("ART_HEROES_ONLY") or "").lower() in ("1", "true", "yes")
# Provider preference: OpenAI gpt-image-1 first (best at distinct per-tool
# characters; Gemini image gen is paywalled behind blocked Google billing, and
# Flux/Pollinations regressed every hero to a generic caped figure).
PROVIDER = os.environ.get("ART_PROVIDER") or (
    "openai" if OPENAI_KEY else "gemini" if GEM_KEYS else "pollinations")
ARTLOG = ROOT / ".github" / "last-art.txt"
_gem_idx = 0
LAST_ERR = ""                                   # last generator error, for the log
W = H = 1024

BASE = (
    "Bold comic book illustration, single full-body character, thick black ink outlines, "
    "cel shading, halftone accents, highly detailed, centered composition, plain solid white "
    "background, no text, no words, no real brand logos, no watermark, no signature."
)
# Heroes allow lettering (name banner) + a chest emblem, so they DON'T inherit
# BASE's "no text" clause — but still forbid copying any real company logo.
# gpt-image-1 renders short text + simple symbols reliably (Flux could not,
# which is why emblems used to be vector overlays only).
HERO_BASE = (
    "High-quality 3D ANIMATED movie character in the style of a Pixar / DreamWorks / Disney "
    "CGI animated film — polished 3D render, smooth surfaces, soft cinematic studio lighting, "
    "subtle subsurface scattering, gentle ambient occlusion, expressive slightly stylised "
    "proportions, vibrant full colour (NOT a drawing, NOT a comic ink sketch, NOT flat 2D, "
    "NOT greyscale). ONE complete full-body character shown HEAD TO TOE, zoomed OUT so the whole "
    "figure is small enough to sit fully inside the frame: the entire head and hair with clear "
    "empty space ABOVE it, and both feet with clear empty space BELOW them. Absolutely nothing "
    "cropped — do NOT cut off the top of the head, the hands, or the feet; leave a comfortable "
    "margin on all four sides. Wide full shot of the standing character, not a close-up. NO "
    "background at all "
    "— the character is fully isolated/cut out on a transparent background, with no scenery, no "
    "floor, no backdrop, no glow cloud behind them. No watermark, no signature. Do NOT reproduce "
    "any real company logo; any emblem "
    "must be an original invented symbol. No text, no words, no lettering, no captions, "
    "no name banner anywhere in the image."
)
# The distinct look comes from each tool's ARCHETYPE (passed in per hero), not a
# single fixed silhouette. Keep only the shared "original + bright + hopeful"
# framing here so every hero reads different.
HERO_STYLE = (HERO_BASE + " An original animated superhero, bright and hopeful, uplifting heroic "
    "mood, warm optimistic lighting. Fully original design, NOT Superman, NOT Batman, no generic "
    "cape-and-trunks default.")
# Villains: the opposite. Dark, ominous, hopeless.
VILLAIN_STYLE = (BASE + " Dark ominous menacing mood, grim shadows, cold sinister lighting, "
    "hopeless and threatening atmosphere.")


def _seed(name):
    return zlib.crc32(name.encode("utf-8")) % 1_000_000


# Flux follows colour NAMES far better than hex codes.
_NAMED = {
    "red": (220, 40, 40), "orange": (230, 130, 60), "coral": (217, 119, 87),
    "gold": (232, 185, 60), "yellow": (250, 210, 70), "green": (30, 180, 100),
    "teal": (42, 161, 152), "blue": (70, 130, 240), "indigo": (100, 90, 220),
    "purple": (150, 90, 230), "pink": (250, 100, 150), "silver": (170, 170, 175),
    "cyan": (0, 196, 204),
}


def color_name(hexstr):
    try:
        h = hexstr.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except (ValueError, IndexError):
        return "bright"
    return min(_NAMED, key=lambda n: sum((a - c) ** 2 for a, c in zip(_NAMED[n], (r, g, b))))


def gen_pollinations(prompt, dest, retries=5):
    """Pollinations Flux: GET the prompt URL, save the returned image bytes."""
    url = (f"https://image.pollinations.ai/prompt/{quote(prompt)}"
           f"?width={W}&height={H}&nologo=true&model={MODEL}&seed={_seed(dest.stem)}")
    last = ""
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=240)
        except requests.RequestException as e:
            last = str(e); time.sleep(6 * (attempt + 1)); continue
        ct = r.headers.get("content-type", "")
        if r.status_code < 400 and ct.startswith("image") and len(r.content) > 10000:
            dest.write_bytes(r.content)
            return True
        last = f"{r.status_code} {ct} {len(r.content)}b"
        time.sleep(8 * (attempt + 1))
    print(f"  FAILED {dest.name}: {last}", file=sys.stderr)
    return False


def gen_gemini(prompt, dest, retries=None):
    """Gemini image model via the /v1beta/interactions endpoint: returns a
    base64 PNG under steps[].content[] (type=image). Rotates keys on quota."""
    global _gem_idx, LAST_ERR
    retries = retries if retries is not None else 2 * max(1, len(GEM_KEYS))
    last = ""
    for attempt in range(retries):
        key = GEM_KEYS[_gem_idx % len(GEM_KEYS)]
        try:
            r = requests.post(
                "https://generativelanguage.googleapis.com/v1beta/interactions",
                headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                json={"model": GEMINI_IMAGE_MODEL,
                      "input": [{"type": "text", "text": prompt}],
                      "response_format": {"type": "image", "aspect_ratio": "1:1"}},
                timeout=180)
        except requests.RequestException as e:
            last = str(e); time.sleep(3 * (attempt + 1)); continue
        if r.status_code < 400:
            for step in r.json().get("steps", []):
                for c in step.get("content", []):
                    if c.get("type") == "image" and c.get("data"):
                        dest.write_bytes(base64.b64decode(c["data"]))
                        return True
            last = "no image in response"
        else:
            last = f"{r.status_code}: {r.text[:200]}"
            if r.status_code == 429 and len(GEM_KEYS) > 1:
                _gem_idx += 1                       # quota hit: next key in pool
        time.sleep(5 * (attempt + 1))
    LAST_ERR = last
    print(f"  FAILED {dest.name}: {last}", file=sys.stderr)
    return False


def gen_openai(prompt, dest, retries=3):
    """OpenAI gpt-image-1 via /v1/images/generations: always returns a base64
    PNG under data[0].b64_json. Follows distinct per-tool prompts far better
    than Flux, and OpenAI billing sidesteps the blocked Google payment flow."""
    global LAST_ERR
    is_dalle = OPENAI_IMAGE_MODEL.startswith("dall-e")
    # Portrait by default: a standing full-body hero fits head-to-toe far better
    # in 1024x1536 than in a square (square cropped heads + feet). dall-e-3 uses
    # 1024x1792 for portrait; gpt-image-1 uses 1024x1536.
    size = os.environ.get("OPENAI_IMAGE_SIZE") or ("1024x1792" if is_dalle else "1024x1536")
    body = {"model": OPENAI_IMAGE_MODEL, "prompt": prompt, "size": size, "n": 1}
    # NOTE: do NOT send response_format — this endpoint rejects it ("unknown
    # parameter"). dall-e-3 then returns a URL (data[0].url); gpt-image-1 returns
    # base64 (data[0].b64_json). We handle whichever comes back below.
    # dall-e-3 (no org verification needed) uses standard|hd; gpt-image-1 uses
    # low|medium|high|auto.
    body["quality"] = ("hd" if OPENAI_IMAGE_QUALITY == "high" else "standard") \
        if is_dalle else OPENAI_IMAGE_QUALITY
    if not is_dalle:
        # gpt-image-1 can render a real transparent background — far cleaner than
        # keying a beige/gradient backdrop afterwards (which left a cream halo).
        body["background"] = "transparent"
        body["output_format"] = "png"
    last = ""
    for attempt in range(retries):
        try:
            r = requests.post(
                "https://api.openai.com/v1/images/generations",
                headers={"Authorization": f"Bearer {OPENAI_KEY}",
                         "Content-Type": "application/json"},
                json=body, timeout=180)
        except requests.RequestException as e:
            last = str(e); time.sleep(4 * (attempt + 1)); continue
        if r.status_code < 400:
            data = r.json().get("data", [])
            item = data[0] if data else {}
            if item.get("b64_json"):
                dest.write_bytes(base64.b64decode(item["b64_json"]))
                return True
            if item.get("url"):
                try:
                    img = requests.get(item["url"], timeout=120)
                    if img.status_code < 400 and len(img.content) > 10000:
                        dest.write_bytes(img.content)
                        return True
                    last = f"image download {img.status_code} {len(img.content)}b"
                except requests.RequestException as e:
                    last = f"image download error: {e}"
            else:
                last = "no image in response"
        else:
            last = f"{r.status_code}: {r.text[:200]}"
        time.sleep(5 * (attempt + 1))
    LAST_ERR = last
    print(f"  FAILED {dest.name}: {last}", file=sys.stderr)
    return False


def gen_image(prompt, dest):
    """Dispatch to the configured provider (OpenAI preferred; Gemini, then Flux)."""
    if PROVIDER == "openai" and OPENAI_KEY:
        return gen_openai(prompt, dest)
    if PROVIDER == "gemini" and GEM_KEYS:
        return gen_gemini(prompt, dest)
    return gen_pollinations(prompt, dest)


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def main():
    uni = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    # Every tool we make videos about gets a hero avatar. roster.json is the
    # full list; universe heroes add hand-written powers for a richer prompt.
    powers = {h["tool"]: h.get("power") for h in uni["heroes"]}
    tools = json.loads(ROSTER.read_text(encoding="utf-8"))["tools"] if ROSTER.exists() else uni["heroes"]
    jobs = []
    for h in tools:
        s = slugify(h["tool"])
        col = color_name(h["color"])
        power = powers.get(h["tool"]) or f"the powers of the {h['tool']} AI tool"
        # The archetype gives each hero its own silhouette/theme so they don't
        # all look alike; fall back to a generic line for any tool without one.
        archetype = h.get("archetype") or "an original futuristic superhero"
        base = (f"{HERO_STYLE} The hero is called {h['alias']}, depicted as {archetype}. "
                f"STRONG {col} colour scheme: the costume is predominantly bright {col}, with "
                f"{col} energy and {col} accents throughout, vividly coloured (do NOT render "
                f"greyscale). On the chest, a single original iconic emblem symbolising their "
                f"power ({power}), drawn as a clean {col} glyph (an invented symbol, NOT a real "
                f"logo). Their power: {power}.")
        jobs.append((OUT / f"hero-{s}-idle.png", base + " Confident, calm, hopeful heroic stance, facing the viewer, standing tall."))
        jobs.append((OUT / f"hero-{s}-action.png", base + " Dynamic mid-action pose, unleashing their power with a bright energy burst."))
    if not HEROES_ONLY:
        for v in uni["villains"]:
            s = slugify(v["name"])
            base = (f"{VILLAIN_STYLE} An original comic supervillain called {v['name']}, a monstrous "
                    f"embodiment of this menace: {v['menace']}. Dark, ominous palette with sickly accents.")
            jobs.append((OUT / f"villain-{s}-menace.png", base + " Towering menacing pose, attacking toward the viewer."))
            jobs.append((OUT / f"villain-{s}-defeated.png", base + " Defeated: collapsed, crumbling and dissolving away, drained of power."))
    done = skipped = failed = 0
    for dest, prompt in jobs:
        if dest.exists() and dest.stat().st_size > 10000:
            skipped += 1
            continue
        if ART_LIMIT and (done + failed) >= ART_LIMIT:
            break                           # smoke-test cap: count attempts, not just
                                            # successes, so failures can't grind the batch
        print(f"generating {dest.name} ...")
        if gen_image(prompt, dest):
            done += 1
        else:
            failed += 1
        time.sleep(2)                       # be gentle with the free tier
    print(f"art: {done} generated, {skipped} already present, {failed} failed")
    # Committed receipt so failures are visible from git (job logs need admin).
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        ARTLOG.parent.mkdir(parents=True, exist_ok=True)
        active_model = {"openai": OPENAI_IMAGE_MODEL, "gemini": GEMINI_IMAGE_MODEL,
                        "pollinations": MODEL}.get(PROVIDER, PROVIDER)
        ARTLOG.write_text(
            f"{ts} provider={PROVIDER} model={active_model} "
            f"done={done} skipped={skipped} failed={failed} "
            f"last_err={' '.join(LAST_ERR.split())[:240] or 'none'}\n", encoding="utf-8")
    except Exception as e:
        print(f"art log write failed: {e}", file=sys.stderr)
    # Failures are fine: rerun later, existing art is skipped. Only fail the
    # run when nothing at all could be generated.
    if done == 0 and skipped == 0:
        sys.exit("no art generated")


if __name__ == "__main__":
    main()
