#!/usr/bin/env python3
"""Local batch runner for screen-capture demo clips (owner's PC ONLY — see
screen_capture.py's docstring: two of the three candidate tools tried hit
bot walls from a cold Playwright launch; imgupscaler.ai, tried third, is the
one confirmed to actually work, but has a low shared free-tier credit quota
— do not run this in a tight loop, see screen_capture.py's quota caveat).

Deliberately decoupled from GitHub Actions: a persistent self-hosted runner
would open a standing remote-code-execution channel from GitHub onto the
owner's PC, which is a bigger security footprint than this needs. Instead:
run this manually, or on a Windows Task Scheduler job, on the owner's PC. It
captures a small batch of clips with screen_capture.py, uploads each as a
GitHub Release asset (same public-URL staging pattern crosspost.py uses for
Reels — but ACCUMULATING: assets are never pruned, this is a growing
library, not a one-shot post), and writes a small JSON manifest
(capture_library.json, committed) recording each clip's public URL and
source, so the render pipeline (future work) can pick one — it never runs
Playwright itself, so it stays on ordinary GitHub-hosted runners.

imgupscaler-upscale is an UPLOAD task (needs a source photo, not a text
prompt), so this batch runner sources one from the Pexels photo API per
clip — same free key render_video.py already uses for b-roll, different
endpoint (photos, not videos).

Env: GITHUB_TOKEN, GITHUB_REPOSITORY (same as crosspost.py's staging step),
PEXELS_API_KEY (source photos to upscale).
CLI: python capture_batch.py [--count N]   (default 2 clips per run — keep
small given the shared credit quota)
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
PX_KEY = os.environ.get("PEXELS_API_KEY")
RELEASE_TAG = "capture-library"
TASK_NAME = "imgupscaler-upscale"

# Search terms for source photos: varied subjects give varied, watchable
# before/after upscales. Portraits and fine detail (animals, text, buildings)
# show the upscale effect more visibly than flat/plain subjects.
PROMPT_POOL = [
    "old family photograph",
    "vintage portrait black and white",
    "small dog close up",
    "city skyline at night",
    "grandmother smiling",
    "antique car",
    "mountain landscape",
    "street market crowd",
]


def load_manifest():
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"clips": []}


def save_manifest(m):
    MANIFEST.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")


def pick_prompts(manifest, count):
    """Prefer search terms not already in the library; once exhausted, allow
    repeats (a different photo still gets returned) rather than stalling the
    batch. Pure function of state, easy to test."""
    used = {c["prompt"] for c in manifest["clips"]}
    fresh = [p for p in PROMPT_POOL if p not in used]
    pool = fresh if fresh else list(PROMPT_POOL)
    random.shuffle(pool)
    return pool[:count]


def fetch_pexels_photo(query, dest):
    """Download one Pexels photo matching `query` to `dest`. Returns True on
    success, False if no result (best-effort, like render_video.pexels_clip)."""
    if not PX_KEY:
        return False
    r = requests.get(
        "https://api.pexels.com/v1/search",
        params={"query": query, "per_page": 5, "orientation": "portrait"},
        headers={"Authorization": PX_KEY}, timeout=30)
    if r.status_code >= 400:
        return False
    photos = r.json().get("photos", [])
    if not photos:
        return False
    url = photos[0]["src"]["large"]
    with requests.get(url, stream=True, timeout=60) as dl:
        if dl.status_code >= 400:
            return False
        with open(dest, "wb") as f:
            for chunk in dl.iter_content(1 << 16):
                f.write(chunk)
    return Path(dest).stat().st_size > 5000


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
    if not PX_KEY:
        sys.exit("PEXELS_API_KEY must be set (source photos for the upscale demo)")
    count = 2      # small default: imgupscaler's free credit pool is shared/limited
    if "--count" in sys.argv:
        count = int(sys.argv[sys.argv.index("--count") + 1])

    api = f"https://api.github.com/repos/{GH_REPO}"
    h = {"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json"}

    manifest = load_manifest()
    prompts = pick_prompts(manifest, count)
    WORK.mkdir(parents=True, exist_ok=True)
    release = _get_or_create_release(api, h)

    made = 0
    for query in prompts:
        photo = WORK / f"source_{int(time.time())}.jpg"
        print(f"fetching source photo: {query}")
        if not fetch_pexels_photo(query, photo):
            print(f"  no Pexels photo for {query!r}; skipping", file=sys.stderr)
            continue
        out = WORK / f"clip_{int(time.time())}.mp4"
        print(f"capturing [{TASK_NAME}]")
        try:
            capture(TASK_NAME, photo, out)
        except Exception as e:
            print(f"  capture failed ({e}); skipping this photo", file=sys.stderr)
            continue
        finally:
            photo.unlink(missing_ok=True)
        try:
            url = upload_clip(out, api, h, release)
        except Exception as e:
            print(f"  upload failed ({e}); keeping local file, not recorded", file=sys.stderr)
            continue
        manifest["clips"].append({
            "task": TASK_NAME, "prompt": query, "url": url,
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
