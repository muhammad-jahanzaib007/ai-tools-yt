#!/usr/bin/env python3
"""Phase B: generate the Toolverse character art via Gemini image generation.

One-time batch (idempotent: existing files are skipped). For every hero in
automation/universe.json: an idle pose and an attack pose. For every villain:
a menacing pose and a defeated pose. Committed to assets/toolverse/ so
episodes reuse the same art forever = consistent characters at zero cost.

Env: GEMINI_API_KEY (+ optional GEMINI_API_KEY_2), GEMINI_IMAGE_MODEL.
"""
import base64
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "toolverse"
UNIVERSE = ROOT / "automation" / "universe.json"

KEYS = [k for k in (os.environ.get("GEMINI_API_KEY"),
                    os.environ.get("GEMINI_API_KEY_2")) if k]
MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")

STYLE = (
    "Bold comic book illustration, single full-body character, dynamic pose, thick black "
    "outlines, cel shading, halftone accents, vibrant colors, centered composition, "
    "PLAIN SOLID WHITE background, no text, no words, no logos, no watermark."
)

_key_idx = 0


def gen_image(prompt, dest, retries=4):
    global _key_idx
    last = ""
    for attempt in range(retries * max(1, len(KEYS))):
        key = KEYS[_key_idx % len(KEYS)]
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
                params={"key": key},
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"responseModalities": ["IMAGE"]}},
                timeout=180,
            )
        except requests.RequestException as e:
            last = str(e); time.sleep(5); continue
        if r.status_code < 400:
            try:
                parts = r.json()["candidates"][0]["content"]["parts"]
                data = next(p["inlineData"]["data"] for p in parts if "inlineData" in p)
            except (KeyError, IndexError, StopIteration):
                last = "no image in response"; time.sleep(4); continue
            dest.write_bytes(base64.b64decode(data))
            return True
        last = f"{r.status_code}: {r.text[:160]}"
        if r.status_code == 429 and len(KEYS) > 1:
            _key_idx += 1
            print(f"  quota hit; rotating key", file=sys.stderr)
            continue
        if r.status_code in (429, 500, 502, 503):
            time.sleep(10 * (attempt + 1)); continue
        break
    print(f"  FAILED {dest.name}: {last}", file=sys.stderr)
    return False


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def main():
    if not KEYS:
        sys.exit("GEMINI_API_KEY must be set")
    uni = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = []
    for h in uni["heroes"]:
        s = slugify(h["tool"])
        base = (f"{STYLE} An original superhero character called {h['alias']}, the heroic "
                f"personification of an AI tool. Costume dominated by the color {h['color']}. "
                f"Their power: {h['power']}. An original character, NOT a company logo or mascot.")
        jobs.append((OUT / f"hero-{s}-idle.png", base + " Confident heroic idle stance, facing the viewer."))
        jobs.append((OUT / f"hero-{s}-action.png", base + " Explosive mid-attack action pose, unleashing their power."))
    for v in uni["villains"]:
        s = slugify(v["name"])
        base = (f"{STYLE} An original comic supervillain called {v['name']}, a monstrous "
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
