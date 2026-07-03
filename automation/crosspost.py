#!/usr/bin/env python3
"""
Phase 4 (optional): cross-post the freshly rendered Short to Instagram Reels
and Facebook Reels, reusing the same output/*.mp4 the YouTube upload used.

Design notes
------------
- Instagram's Graph API publishes Reels from a PUBLIC video URL (it fetches the
  file itself); it does NOT accept a file upload. In CI the mp4 is a local file,
  so we first stage it as a GitHub Release asset (public repo -> public raw URL)
  and hand that URL to Instagram. Facebook Reels can take the same hosted URL.
- Everything is env-gated: if the Meta secrets are absent the script prints a
  notice and exits 0, so it can sit in the pipeline before creds exist and never
  break a run. Same reason every network call is wrapped and best-effort.

Required env (repo secrets) to actually post:
  META_PAGE_TOKEN   long-lived Page access token          (IG + FB)
  IG_USER_ID        Instagram Business account id (linked to the Page)
  FB_PAGE_ID        Facebook Page id
  TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_REFRESH_TOKEN   (TikTok)
Provided automatically by Actions (for staging the public URL):
  GITHUB_TOKEN, GITHUB_REPOSITORY
Optional:
  CROSSPOST_TARGETS   comma list, default "ig,fb"  (add "tt" for TikTok)
  TIKTOK_PRIVACY      "SELF_ONLY" (default, pre-audit) or "PUBLIC_TO_EVERYONE"
  DRY_RUN             "1" = build caption + stage, but do not publish

TikTok note: an unaudited app can only post SELF_ONLY (private). Flip
TIKTOK_PRIVACY to PUBLIC_TO_EVERYONE only after the app passes TikTok audit.
"""

import os
import sys
import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
BRIEFS = ROOT / "briefs"
TELEMETRY = ROOT / ".github" / "last-crosspost.txt"
GRAPH = "https://graph.facebook.com/v21.0"

TOKEN = os.environ.get("META_PAGE_TOKEN")
IG_USER_ID = os.environ.get("IG_USER_ID")
FB_PAGE_ID = os.environ.get("FB_PAGE_ID")
TT_KEY = os.environ.get("TIKTOK_CLIENT_KEY")
TT_SECRET = os.environ.get("TIKTOK_CLIENT_SECRET")
TT_REFRESH = os.environ.get("TIKTOK_REFRESH_TOKEN")
TT_PRIVACY = os.environ.get("TIKTOK_PRIVACY", "SELF_ONLY")
GH_TOKEN = os.environ.get("GITHUB_TOKEN")
GH_REPO = os.environ.get("GITHUB_REPOSITORY")            # "owner/name"
TARGETS = [t.strip() for t in os.environ.get("CROSSPOST_TARGETS", "ig,fb").split(",") if t.strip()]
DRY_RUN = os.environ.get("DRY_RUN") == "1"


def log(*a):
    print("[crosspost]", *a, file=sys.stderr)


def write_telemetry(video, results):
    """Commit a one-line per-run receipt like the other pipeline stages, so the
    IG/FB/TikTok outcome is visible from git without digging the Actions log.
    results = dict platform -> "ok:<id>" | "fail:<reason>" | "skip"."""
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    name = video.name if video else "none"

    def clean(v):
        return " ".join(str(v).split())[:160]

    parts = " ".join(f"{p}={clean(results.get(p, 'skip'))}" for p in ("ig", "fb", "tt"))
    try:
        TELEMETRY.parent.mkdir(parents=True, exist_ok=True)
        TELEMETRY.write_text(f"{ts} {name} {parts}\n", encoding="utf-8")
    except Exception as e:
        log(f"telemetry write failed: {e}")


def newest_video():
    mp4s = sorted(OUT.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    return mp4s[0] if mp4s else None


def build_caption(brief):
    """Social caption: hook-y title + hashtags. Links aren't clickable on IG/TikTok
    so we push viewers to the bio instead of pasting dead URLs."""
    title = (brief.get("title") or "").strip()

    def _hash(s):
        h = "".join(ch for ch in s if ch.isalnum())
        return f"#{h}" if h else ""

    seen, tags = set(), []
    for h in (["#Reels", "#Shorts"]
              + [_hash(l["name"]) for l in brief.get("links", [])]
              + [_hash(t) for t in brief.get("tags", [])]
              + ["#AItools", "#AI", "#technology"]):
        k = h.lower()
        if h and k not in seen:
            seen.add(k)
            tags.append(h)
    body = title
    if brief.get("links"):
        body += "\n\nFull battle + tool links in our bio \U0001F517"
    body += "\n\n" + " ".join(tags[:20])
    return body.strip()[:2200]


# --- stage the mp4 at a public URL via a GitHub Release asset -----------------

def stage_public_url(video: Path):
    """Upload the mp4 as a Release asset on the public repo and return its
    browser_download_url (public, no auth). Reuses one 'crosspost' release."""
    if not (GH_TOKEN and GH_REPO):
        raise RuntimeError("GITHUB_TOKEN / GITHUB_REPOSITORY needed to stage a public URL")
    api = f"https://api.github.com/repos/{GH_REPO}"
    h = {"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json"}
    tag = "crosspost-assets"
    # get-or-create the release
    r = requests.get(f"{api}/releases/tags/{tag}", headers=h)
    if r.status_code == 404:
        r = requests.post(f"{api}/releases", headers=h, json={
            "tag_name": tag, "name": "Crosspost assets",
            "body": "Auto-staged Reels videos for IG/FB cross-posting.",
            "prerelease": True})
    r.raise_for_status()
    rel = r.json()
    name = video.name
    # remove an old asset with the same name (idempotent re-runs)
    for a in rel.get("assets", []):
        if a["name"] == name:
            requests.delete(f"{api}/releases/assets/{a['id']}", headers=h)
    up = rel["upload_url"].split("{")[0]
    with open(video, "rb") as f:
        r = requests.post(f"{up}?name={name}", headers={**h, "Content-Type": "video/mp4"}, data=f)
    r.raise_for_status()
    return r.json()["browser_download_url"]


# --- Instagram Reels ----------------------------------------------------------

def post_instagram(video_url, caption):
    # 1. create a REELS media container from the public url
    r = requests.post(f"{GRAPH}/{IG_USER_ID}/media", data={
        "media_type": "REELS", "video_url": video_url,
        "caption": caption, "access_token": TOKEN})
    r.raise_for_status()
    cid = r.json()["id"]
    # 2. poll until the container finishes processing (IG pulls + transcodes)
    for _ in range(30):
        time.sleep(10)
        s = requests.get(f"{GRAPH}/{cid}", params={
            "fields": "status_code", "access_token": TOKEN}).json()
        code = s.get("status_code")
        if code == "FINISHED":
            break
        if code == "ERROR":
            raise RuntimeError(f"IG container error: {s}")
    else:
        raise RuntimeError("IG container did not finish in time")
    # 3. publish
    r = requests.post(f"{GRAPH}/{IG_USER_ID}/media_publish", data={
        "creation_id": cid, "access_token": TOKEN})
    r.raise_for_status()
    return r.json().get("id")


# --- Facebook Reels -----------------------------------------------------------

def post_facebook(video_url, caption):
    # start -> obtain a video id
    r = requests.post(f"{GRAPH}/{FB_PAGE_ID}/video_reels", data={
        "upload_phase": "start", "access_token": TOKEN})
    r.raise_for_status()
    vid = r.json()["video_id"]
    # upload by hosted-file url (rupload accepts a file_url header)
    r = requests.post(f"https://rupload.facebook.com/video-upload/v21.0/{vid}",
                      headers={"Authorization": f"OAuth {TOKEN}", "file_url": video_url})
    r.raise_for_status()
    # finish + publish
    r = requests.post(f"{GRAPH}/{FB_PAGE_ID}/video_reels", data={
        "upload_phase": "finish", "video_id": vid,
        "video_state": "PUBLISHED", "description": caption,
        "access_token": TOKEN})
    r.raise_for_status()
    return vid


# --- TikTok (Content Posting API, Direct Post via file upload) ----------------

def _tiktok_access_token():
    r = requests.post("https://open.tiktokapis.com/v2/oauth/token/", data={
        "client_key": TT_KEY, "client_secret": TT_SECRET,
        "grant_type": "refresh_token", "refresh_token": TT_REFRESH})
    r.raise_for_status()
    return r.json()["access_token"]


def post_tiktok(video: Path, caption):
    """Direct-post the local mp4 to TikTok. FILE_UPLOAD (not PULL_FROM_URL) so we
    don't need TikTok domain verification. Pre-audit this only lands as SELF_ONLY."""
    at = _tiktok_access_token()
    h = {"Authorization": f"Bearer {at}", "Content-Type": "application/json"}
    size = video.stat().st_size
    # TikTok requires querying creator posting eligibility before init; it also
    # surfaces the clearest permission errors, so a 403 here tells us the reason.
    ci = requests.post("https://open.tiktokapis.com/v2/post/publish/creator_info/query/", headers=h)
    if not ci.ok:
        raise RuntimeError(f"creator_info {ci.status_code}: {ci.text[:300]}")
    # single-chunk upload (Shorts are small); TikTok caps a chunk at 64MB
    init = requests.post(
        "https://open.tiktokapis.com/v2/post/publish/video/init/", headers=h,
        json={"post_info": {"title": caption[:2200], "privacy_level": TT_PRIVACY,
                            "disable_comment": False, "disable_duet": False, "disable_stitch": False},
              "source_info": {"source": "FILE_UPLOAD", "video_size": size,
                              "chunk_size": size, "total_chunk_count": 1}})
    if not init.ok:
        raise RuntimeError(f"init {init.status_code}: {init.text[:300]}")
    d = init.json()["data"]
    upload_url, publish_id = d["upload_url"], d["publish_id"]
    with open(video, "rb") as f:
        requests.put(upload_url, data=f.read(), headers={
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes 0-{size-1}/{size}",
            "Content-Length": str(size)}).raise_for_status()
    # poll publish status
    for _ in range(30):
        time.sleep(10)
        s = requests.post("https://open.tiktokapis.com/v2/post/publish/status/fetch/",
                          headers=h, json={"publish_id": publish_id}).json()
        st = s.get("data", {}).get("status")
        if st in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
            return publish_id
        if st == "FAILED":
            raise RuntimeError(f"TikTok publish failed: {s}")
    raise RuntimeError("TikTok publish did not finish in time")


def main():
    do_ig = "ig" in TARGETS and TOKEN and IG_USER_ID
    do_fb = "fb" in TARGETS and TOKEN and FB_PAGE_ID
    do_tt = "tt" in TARGETS and TT_KEY and TT_SECRET and TT_REFRESH
    if not (do_ig or do_fb or do_tt):
        log("no platform creds present for enabled targets - skipping cross-post.")
        return
    video = newest_video()
    if not video:
        log("no rendered video found - skipping.")
        return
    brief_path = BRIEFS / f"{video.stem}.json"
    brief = json.loads(brief_path.read_text(encoding="utf-8")) if brief_path.exists() else {}
    caption = build_caption(brief)
    log(f"video={video.name}")
    log(f"caption={caption!r}")

    results = {}

    # IG needs a public URL; FB reuses it. TikTok uploads the local file directly.
    public_url = None
    if do_ig or do_fb:
        try:
            public_url = stage_public_url(video)
            log(f"staged public url: {public_url}")
        except Exception as e:
            log(f"staging failed, IG/FB disabled this run: {e}")
            reason = f"fail:staging {e}"
            if do_ig:
                results["ig"] = reason
            if do_fb:
                results["fb"] = reason
            do_ig = do_fb = False

    if DRY_RUN:
        log("DRY_RUN=1 - staged only, not publishing.")
        write_telemetry(video, {p: "dryrun" for p in ("ig", "fb", "tt")
                                if {"ig": do_ig, "fb": do_fb, "tt": do_tt}[p]})
        return

    if do_ig:
        try:
            rid = post_instagram(public_url, caption)
            log("instagram reel id:", rid)
            results["ig"] = f"ok:{rid}"
        except Exception as e:
            log(f"instagram post failed: {e}")
            results["ig"] = f"fail:{e}"
    if do_fb:
        try:
            vid = post_facebook(public_url, caption)
            log("facebook reel id:", vid)
            results["fb"] = f"ok:{vid}"
        except Exception as e:
            log(f"facebook post failed: {e}")
            results["fb"] = f"fail:{e}"
    if do_tt:
        try:
            pid = post_tiktok(video, caption)
            log("tiktok publish id:", pid)
            results["tt"] = f"ok:{pid}"
        except Exception as e:
            log(f"tiktok post failed: {e}")
            results["tt"] = f"fail:{e}"

    write_telemetry(video, results)


if __name__ == "__main__":
    main()
