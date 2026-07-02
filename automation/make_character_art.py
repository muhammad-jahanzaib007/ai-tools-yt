#!/usr/bin/env python3
"""Phase B: generate the Toolverse character art via Pollinations (free Flux).

One-time batch (idempotent: existing files are skipped). For every hero in
automation/universe.json: an idle pose and an attack pose. For every villain:
a menacing pose and a defeated pose. Committed to assets/toolverse/ so
episodes reuse the same art forever = high quality, zero cost, no API key.

Pollinations serves Flux with no auth. Deterministic per file via a seed so
reruns reproduce the same character. Env: POLLINATIONS_MODEL (default flux).
"""
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

MODEL = os.environ.get("POLLINATIONS_MODEL", "flux")
W = H = 1024

BASE = (
    "Bold comic book illustration, single full-body character, thick black ink outlines, "
    "cel shading, halftone accents, highly detailed, centered composition, plain solid white "
    "background, no text, no words, no real brand logos, no watermark, no signature."
)
# Heroes: sleek modern tech-armor (deliberately NOT the Superman/Batman
# cape-and-trunks silhouette Flux defaults to), bright and hopeful.
HERO_STYLE = (BASE + " A sleek modern high-tech superhero in a form-fitting armored suit with "
    "glowing neon energy lines and a smooth helmet with a glowing visor. NO cape, NO trunks, "
    "not Superman, not Batman, an original futuristic design. Uplifting hopeful mood, bright "
    "optimistic lighting, radiant glow, cool confident and inspiring.")
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


def gen_image(prompt, dest, retries=5):
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
        base = (f"{HERO_STYLE} An original superhero character called {h['alias']}. Costume and "
                f"cape are primarily {col} (a {col} colour scheme), with a clean plain chest and "
                "no chest logo (an emblem is added separately). Not Superman, not a diamond crest, "
                f"a fully original hero design. Their power: {power}.")
        jobs.append((OUT / f"hero-{s}-idle.png", base + " Confident, calm, hopeful heroic stance, facing the viewer, standing tall."))
        jobs.append((OUT / f"hero-{s}-action.png", base + " Dynamic mid-action pose, unleashing their power with a bright energy burst."))
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
        print(f"generating {dest.name} ...")
        if gen_image(prompt, dest):
            done += 1
        else:
            failed += 1
        time.sleep(2)                       # be gentle with the free tier
    print(f"art: {done} generated, {skipped} already present, {failed} failed")
    # Failures are fine: rerun later, existing art is skipped. Only fail the
    # run when nothing at all could be generated.
    if done == 0 and skipped == 0:
        sys.exit("no art generated")


if __name__ == "__main__":
    main()
