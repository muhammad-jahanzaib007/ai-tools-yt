#!/usr/bin/env python3
"""Local batch runner for screen-capture demo clips (owner's PC ONLY — see
screen_capture.py's docstring: perchance.org sits behind a Cloudflare
bot-wall from a GitHub Actions cloud IP, confirmed 2026-07-22 via a live
diagnostic run that returned a real "Performing security verification"
Turnstile page. This only works from a residential IP.

Deliberately decoupled from GitHub Actions: a persistent self-hosted runner
would open a standing remote-code-execution channel from GitHub onto the
owner's PC, which is a bigger security footprint than this needs. Instead:
run this manually, or on a Windows Task Scheduler job, on the owner's PC. It
captures a small batch of clips with screen_capture.py, uploads each as a
GitHub Release asset (same public-URL staging pattern crosspost.py uses for
Reels — but ACCUMULATING: assets are never pruned, this is a growing
library, not a one-shot post), and writes a small JSON manifest
(capture_library.json, committed) recording each clip's public URL, prompt,
and used state. The render pipeline (future work) reads the manifest and
downloads an unused clip — it never runs Playwright itself, so it stays on
ordinary GitHub-hosted runners.

Env: GITHUB_TOKEN, GITHUB_REPOSITORY (same as crosspost.py's staging step).
CLI: python capture_batch.py [--count N]   (default 3 clips per run)
"""
import json
import os
import random
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from screen_capture import capture  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "automation" / "capture_library.json"
WORK = ROOT / ".render" / "capture_batch"

GH_TOKEN = os.environ.get("GITHUB_TOKEN")
GH_REPO = os.environ.get("GITHUB_REPOSITORY") or "muhammad-jahanzaib007/ai-tools-yt"
RELEASE_TAG = "capture-library"

# Seed prompts: concrete and visual, same "one striking concrete result" rule
# BATTLE_BULLETS already applies to hooks. One task for now (perchance-image);
# add more TASK_LIBRARY entries in screen_capture.py as they're verified live
# (NightCafe was the researched same-prompt pairing candidate for an "X vs Y"
# comparison cut).
PROMPT_POOL = [
    "a golden retriever wearing sunglasses, skateboarding down a city street, sunset, cinematic",
    "a majestic wolf howling on a snowy mountain peak, moonlight, cinematic",
    "a red sports car drifting through neon-lit Tokyo streets at night",
    "an astronaut floating above Earth, reflecting the planet in their visor, cinematic",
    "a steaming bowl of ramen on a rainy Tokyo street stall at night",
    "a treehouse village connected by rope bridges in a glowing forest at dusk",
    "a lighthouse on a rocky cliff during a thunderstorm, dramatic lighting",
    "a dragon curled asleep on a mountain of gold coins in a cave",
]


def load_manifest():
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"clips": []}


def save_manifest(m):
    MANIFEST.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")


def pick_prompts(manifest, count):
    """Prefer prompts not already in the library; once exhausted, allow
    repeats (a different tool run still produces a different image) rather
    than stalling the batch. Pure function of state, easy to test."""
    used = {c["prompt"] for c in manifest["clips"]}
    fresh = [p for p in PROMPT_POOL if p not in used]
    pool = fresh if fresh else list(PROMPT_POOL)
    random.shuffle(pool)
    return pool[:count]


def _get_or_create_release(api, h):
    r = requests.get(f"{api}/releases/tags/{RELEASE_TAG}", headers=h, timeout=30)
    if r.status_code == 404:
        r = requests.post(f"{api}/releases", headers=h, json={
            "tag_name": RELEASE_TAG, "name": "Screen-capture demo library",
            "body": "Accumulating pool of screen-capture demo clips (captured on the "
                     "owner's PC — see automation/screen_capture.py). Consumed by the "
                     "render pipeline; not meant for direct viewing.",
            "prerelease": True}, timeout=30)
    r.raise_for_status()
    return r.json()


def upload_clip(path, api, h, release):
    up = release["upload_url"].split("{")[0]
    with open(path, "rb") as f:
        r = requests.post(f"{up}?name={path.name}",
                          headers={**h, "Content-Type": "video/mp4"},
                          data=f, timeout=600)
    r.raise_for_status()
    return r.json()["browser_download_url"]


def main():
    if not GH_TOKEN:
        sys.exit("GITHUB_TOKEN must be set (fine-grained PAT, Contents: Read and write)")
    count = 3
    if "--count" in sys.argv:
        count = int(sys.argv[sys.argv.index("--count") + 1])

    api = f"https://api.github.com/repos/{GH_REPO}"
    h = {"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json"}

    manifest = load_manifest()
    prompts = pick_prompts(manifest, count)
    WORK.mkdir(parents=True, exist_ok=True)
    release = _get_or_create_release(api, h)

    made = 0
    for prompt in prompts:
        task_name = "perchance-image"
        out = WORK / f"clip_{int(time.time())}.mp4"
        print(f"capturing [{task_name}]: {prompt}")
        try:
            capture(task_name, prompt, out)
        except Exception as e:
            print(f"  capture failed ({e}); skipping this prompt", file=sys.stderr)
            continue
        try:
            url = upload_clip(out, api, h, release)
        except Exception as e:
            print(f"  upload failed ({e}); keeping local file, not recorded", file=sys.stderr)
            continue
        manifest["clips"].append({
            "task": task_name, "prompt": prompt, "url": url,
            "captured": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "used": False,
        })
        save_manifest(manifest)      # after each clip: a mid-batch failure keeps earlier wins
        out.unlink(missing_ok=True)
        made += 1
        print(f"  staged: {url}")

    print(f"done: {made} new clip(s), {len(manifest['clips'])} total in library")


if __name__ == "__main__":
    main()
