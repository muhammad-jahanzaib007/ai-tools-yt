#!/usr/bin/env python3
"""
Phase 3: upload the rendered video to YouTube.

Uploads the newest output/*.mp4 with title/description/tags from its brief, sets
the thumbnail, and marks it not-made-for-kids. Auth is OAuth via a long-lived
refresh token (no browser needed at run time).

Required env (set as repo secrets):
  YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
Optional:
  YT_PRIVACY   (default "private"; set "public" or "unlisted")
  YT_CATEGORY  (default "28" = Science & Technology)
"""

import os
import sys
import json
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
BRIEFS = ROOT / "briefs"

CID = os.environ.get("YT_CLIENT_ID")
CSEC = os.environ.get("YT_CLIENT_SECRET")
RT = os.environ.get("YT_REFRESH_TOKEN")
PRIVACY = os.environ.get("YT_PRIVACY") or "private"
CATEGORY = os.environ.get("YT_CATEGORY") or "28"          # Science & Technology


def main():
    if not (CID and CSEC and RT):
        sys.exit("YT_CLIENT_ID, YT_CLIENT_SECRET and YT_REFRESH_TOKEN must be set")

    mp4s = sorted(OUT.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not mp4s:
        sys.exit("no rendered video found in output/")
    video = mp4s[0]
    slug = video.stem
    brief_path = BRIEFS / f"{slug}.json"
    brief = json.loads(brief_path.read_text(encoding="utf-8")) if brief_path.exists() else {}

    title = (brief.get("title") or slug)[:100]
    desc = brief.get("description", "")
    desc = desc.replace("Tools mentioned and links: [AFFILIATE_LINKS]", "").strip()

    # Build the "Tools mentioned" section from the brief's links.
    # Optional: automation/affiliates.json maps a tool name -> your affiliate URL.
    overrides = {}
    aff = ROOT / "automation" / "affiliates.json"
    if aff.exists():
        try:
            raw = json.loads(aff.read_text(encoding="utf-8"))
            overrides = {k.lower(): v.strip() for k, v in raw.items()
                         if not k.startswith("_") and isinstance(v, str) and v.strip()}
        except Exception as e:
            print(f"affiliates.json ignored: {e}", file=sys.stderr)
    links = brief.get("links", [])
    if links:
        rows = [f"{l['name']}: {overrides.get(l['name'].lower(), l['url'])}" for l in links]
        desc = (desc + "\n\nTools mentioned:\n" + "\n".join(rows)).strip()
        if overrides:   # FTC disclosure, only once real affiliate links are in use
            desc += ("\n\nSome links above are affiliate links and may earn the channel a "
                     "commission at no extra cost to you.")

    desc = (desc + "\n\n#AI #AItools #technology").strip()[:4900]
    tags = [t for t in brief.get("tags", []) if t][:15]

    creds = Credentials(
        None, refresh_token=RT, client_id=CID, client_secret=CSEC,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)

    body = {
        "snippet": {"title": title, "description": desc, "tags": tags, "categoryId": CATEGORY},
        "status": {"privacyStatus": PRIVACY, "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(video), chunksize=-1, resumable=True, mimetype="video/mp4")
    print(f"Uploading {video.name}  ({title!r}, privacy={PRIVACY})")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
    vid = resp["id"]
    print(f"Uploaded: https://youtu.be/{vid}")

    thumb = OUT / f"{slug}.jpg"
    if thumb.exists():
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(thumb))).execute()
            print("Thumbnail set.")
        except Exception as e:
            print(f"thumbnail set skipped: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
