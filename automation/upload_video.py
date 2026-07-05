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
PLAYLISTS_JSON = ROOT / "automation" / "playlists.json"

# Each format gets its own playlist; created on first use, id persisted in
# playlists.json (committed by the workflow's record step).
PLAYLIST_TITLES = {
    "battle": "AI Tool Battles",
    "comic": "The AI Toolverse",
    "news": "Daily AI News",
}


def brief_format(brief):
    for f in ("news", "comic", "battle"):
        if brief.get(f):
            return f
    return "battle"


def add_to_playlist(yt, vid, fmt):
    """Create the format's playlist if needed and add the video. Best-effort:
    needs the full youtube scope; a scope-limited token skips with a hint."""
    title = PLAYLIST_TITLES.get(fmt)
    if not title:
        return "skip"
    try:
        m = json.loads(PLAYLISTS_JSON.read_text(encoding="utf-8")) if PLAYLISTS_JSON.exists() else {}
    except Exception:
        m = {}
    try:
        pid = m.get(fmt)
        if not pid:
            resp = yt.playlists().insert(part="snippet,status", body={
                "snippet": {"title": title,
                            "description": f"Snackbyte AI · {title}, new videos daily."},
                "status": {"privacyStatus": "public"},
            }).execute()
            pid = resp["id"]
            m[fmt] = pid
            PLAYLISTS_JSON.write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")
            print(f"Created playlist {title!r} ({pid})")
        yt.playlistItems().insert(part="snippet", body={
            "snippet": {"playlistId": pid,
                        "resourceId": {"kind": "youtube#video", "videoId": vid}},
        }).execute()
        print(f"Added to playlist {title!r}")
        return f"ok:{pid}"
    except Exception as e:
        print(f"playlist step skipped: {e}", file=sys.stderr)
        if "insufficient" in str(e).lower() or "403" in str(e):
            print("hint: re-mint YT_REFRESH_TOKEN with the "
                  "https://www.googleapis.com/auth/youtube scope to enable playlists",
                  file=sys.stderr)
        return "fail"

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

    # Hashtags: #Shorts + one per named tool (topical clustering + search) + a
    # couple of niche tags, then generic. First 3 surface above the title on YT.
    def _hash(s):
        h = "".join(ch for ch in s if ch.isalnum())
        return f"#{h}" if h else ""
    seen, htags = set(), []
    for h in (["#Shorts"]
              + [_hash(l["name"]) for l in links]
              + [_hash(t) for t in brief.get("tags", [])]
              + ["#AItools", "#AI", "#technology"]):
        k = h.lower()
        if h and k not in seen:
            seen.add(k)
            htags.append(h)
    desc = (desc + "\n\n" + " ".join(htags[:12])).strip()[:4900]
    tags = [t for t in brief.get("tags", []) if t][:15]

    # No scopes pinned: the refresh grants whatever the token was authorised
    # with, so a broad token enables playlists without breaking a narrow one.
    creds = Credentials(
        None, refresh_token=RT, client_id=CID, client_secret=CSEC,
        token_uri="https://oauth2.googleapis.com/token",
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
        # retry transient API/network errors: a single 503 here used to kill
        # the run after ~30 min of brief+render work
        status, resp = req.next_chunk(num_retries=5)
    vid = resp["id"]
    url = f"https://youtu.be/{vid}"
    print(f"Uploaded: {url}")

    fmt = brief_format(brief)
    if (OUT / f"{slug}.fallback").exists():
        fmt += "-FALLBACK"        # scene render fell back to plain b-roll;
                                  # also keeps the b-roll video off the playlist
    pl = add_to_playlist(yt, vid, fmt)

    # Private repo: record the URL so it can be read back with git alone.
    try:
        (ROOT / ".github" / "last-upload.txt").write_text(
            f"{video.stem} {PRIVACY} {url} fmt={fmt} pl={pl}\n", encoding="utf-8")
    except Exception:
        pass

    thumb = OUT / f"{slug}.jpg"
    if thumb.exists():
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(thumb))).execute()
            print("Thumbnail set.")
        except Exception as e:
            print(f"thumbnail set skipped: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
