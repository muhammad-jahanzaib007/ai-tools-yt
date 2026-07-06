#!/usr/bin/env python3
"""Create the per-format playlists (idempotent) and record whether the token
has the full youtube scope. This is the exact call upload_video.add_to_playlist
makes, so a `scope=ok` receipt here means `pl=ok` on the next upload.

Required env: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN.
Writes .github/last-token-test.txt and automation/playlists.json.
"""

import os
import sys
import json
import time
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parent.parent
PLAYLISTS_JSON = ROOT / "automation" / "playlists.json"
RECEIPT = ROOT / ".github" / "last-token-test.txt"

PLAYLIST_TITLES = {
    "battle": "AI Tool Battles",
    "comic": "The AI Toolverse",
    "news": "Daily AI News",
}


def main():
    creds = Credentials(
        None, refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
    )
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)

    try:
        m = json.loads(PLAYLISTS_JSON.read_text(encoding="utf-8"))
    except Exception:
        m = {}

    parts, failed = [], False
    for fmt, title in PLAYLIST_TITLES.items():
        if m.get(fmt):
            parts.append(f"{fmt}=exists:{m[fmt]}")
            continue
        try:
            resp = yt.playlists().insert(part="snippet,status", body={
                "snippet": {"title": title,
                            "description": f"Snackbyte AI · {title}, new videos daily."},
                "status": {"privacyStatus": "public"},
            }).execute()
            m[fmt] = resp["id"]
            parts.append(f"{fmt}=created:{resp['id']}")
        except Exception as e:
            failed = True
            parts.append(f"{fmt}=fail:{' '.join(str(e).split())[:120]}")

    if m:
        PLAYLISTS_JSON.write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    verdict = "scope=MISSING (re-mint with the full youtube scope)" if failed else "scope=ok"
    RECEIPT.parent.mkdir(exist_ok=True)
    RECEIPT.write_text(f"{ts} {verdict} {' '.join(parts)}\n", encoding="utf-8")
    print(verdict, *parts)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
