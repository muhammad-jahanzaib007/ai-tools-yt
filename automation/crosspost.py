#!/usr/bin/env python3
"""
Phase 4 (optional): cross-post the freshly rendered Short to Instagram Reels
and Facebook Reels, reusing the same output/*.mp4 the YouTube upload used.
Also stages a copy for the owner to upload to TikTok by hand (see below).

Design notes
------------
- Instagram's Graph API publishes Reels from a PUBLIC video URL (it fetches the
  file itself); it does NOT accept a file upload. In CI the mp4 is a local file,
  so we first stage it as a GitHub Release asset (public repo -> public raw URL)
  and hand that URL to Instagram. Facebook Reels can take the same hosted URL.
- Everything is env-gated: if the Meta secrets are absent the script prints a
  notice and exits 0, so it can sit in the pipeline before creds exist and never
  break a run. Same reason every network call is wrapped and best-effort.

TikTok (2026-07-22): the Developer API review was REJECTED as a matter of
policy — "does not support personal or internal company use," naming our
exact setup. Not fixable by resubmitting, so the auto-post path (Content
Posting API, OAuth, file upload) is gone for good. Instead every rendered
video (same captioned mp4 IG/FB post) is staged to an ACCUMULATING GitHub
Release (tag "tiktok-manual-upload", assets never pruned — a growing queue,
not a one-shot post) and logged in tiktok_manual_queue.json (committed) so
the owner can grab whatever they haven't uploaded yet and upload by hand.
Cleanup (deleting queue entries/assets after uploading) is the owner's call —
not automated, since only the owner knows what's actually been posted.

Required env (repo secrets) to actually post IG/FB:
  META_PAGE_TOKEN   long-lived Page access token          (IG + FB)
  IG_USER_ID        Instagram Business account id (linked to the Page)
  FB_PAGE_ID        Facebook Page id
Provided automatically by Actions (for staging public URLs):
  GITHUB_TOKEN, GITHUB_REPOSITORY
Optional:
  CROSSPOST_TARGETS   comma list, default "ig,fb"
  DRY_RUN             "1" = build caption + stage, but do not publish
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
GH_TOKEN = os.environ.get("GITHUB_TOKEN")
GH_REPO = os.environ.get("GITHUB_REPOSITORY")            # "owner/name"
TARGETS = [t.strip() for t in os.environ.get("CROSSPOST_TARGETS", "ig,fb").split(",") if t.strip()]
DRY_RUN = os.environ.get("DRY_RUN") == "1"
TIKTOK_MANUAL_TAG = "tiktok-manual-upload"
TIKTOK_QUEUE = ROOT / "automation" / "tiktok_manual_queue.json"


def log(*a):
    print("[crosspost]", *a, file=sys.stderr)


def _check(r):
    """Like r.raise_for_status() but include the Graph API error body in the
    message. Meta returns 400 with an OAuthException JSON that names the real
    cause (subcode 190/463 = expired/invalid token, 100 = bad param, etc);
    raise_for_status alone throws a generic 'Bad Request for url' and loses it."""
    if not r.ok:
        raise RuntimeError(f"{r.status_code} {' '.join(r.text.split())[:280]}")
    return r


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
    r = requests.get(f"{api}/releases/tags/{tag}", headers=h, timeout=30)
    if r.status_code == 404:
        r = requests.post(f"{api}/releases", headers=h, json={
            "tag_name": tag, "name": "Crosspost assets",
            "body": "Auto-staged Reels videos for IG/FB cross-posting.",
            "prerelease": True}, timeout=30)
    r.raise_for_status()
    rel = r.json()
    name = video.name
    # prune ALL existing assets: previous runs' videos are already posted,
    # and unpruned assets accumulate in the release forever. Also keeps
    # re-runs of the same slug idempotent.
    for a in rel.get("assets", []):
        requests.delete(f"{api}/releases/assets/{a['id']}", headers=h, timeout=30)
    up = rel["upload_url"].split("{")[0]
    with open(video, "rb") as f:
        r = requests.post(f"{up}?name={name}", headers={**h, "Content-Type": "video/mp4"},
                          data=f, timeout=600)
    r.raise_for_status()
    return r.json()["browser_download_url"]


# --- Instagram Reels ----------------------------------------------------------

def post_instagram(video_url, caption):
    # 1. create a REELS media container from the public url
    r = requests.post(f"{GRAPH}/{IG_USER_ID}/media", data={
        "media_type": "REELS", "video_url": video_url,
        "caption": caption, "access_token": TOKEN}, timeout=60)
    _check(r)
    cid = r.json()["id"]
    # 2. poll until the container finishes processing (IG pulls + transcodes)
    for _ in range(30):
        time.sleep(10)
        s = requests.get(f"{GRAPH}/{cid}", params={
            "fields": "status_code", "access_token": TOKEN}, timeout=30).json()
        code = s.get("status_code")
        if code == "FINISHED":
            break
        if code == "ERROR":
            raise RuntimeError(f"IG container error: {s}")
    else:
        raise RuntimeError("IG container did not finish in time")
    # 3. publish
    r = requests.post(f"{GRAPH}/{IG_USER_ID}/media_publish", data={
        "creation_id": cid, "access_token": TOKEN}, timeout=60)
    _check(r)
    return r.json().get("id")


# --- Facebook Reels -----------------------------------------------------------

def post_facebook(video_url, caption):
    # start -> obtain a video id
    r = requests.post(f"{GRAPH}/{FB_PAGE_ID}/video_reels", data={
        "upload_phase": "start", "access_token": TOKEN}, timeout=60)
    _check(r)
    vid = r.json()["video_id"]
    # upload by hosted-file url (rupload accepts a file_url header; FB fetches
    # the file during this call, so give it the long timeout)
    r = requests.post(f"https://rupload.facebook.com/video-upload/v21.0/{vid}",
                      headers={"Authorization": f"OAuth {TOKEN}", "file_url": video_url},
                      timeout=600)
    _check(r)
    # finish + publish
    r = requests.post(f"{GRAPH}/{FB_PAGE_ID}/video_reels", data={
        "upload_phase": "finish", "video_id": vid,
        "video_state": "PUBLISHED", "description": caption,
        "access_token": TOKEN}, timeout=120)
    _check(r)
    return vid


# --- TikTok: no auto-post (API rejected 2026-07-22) — stage for manual upload -

def _get_or_create_tiktok_release(api, h):
    r = requests.get(f"{api}/releases/tags/{TIKTOK_MANUAL_TAG}", headers=h, timeout=30)
    if r.status_code == 404:
        r = requests.post(f"{api}/releases", headers=h, json={
            "tag_name": TIKTOK_MANUAL_TAG, "name": "TikTok manual-upload queue",
            "body": "Captioned videos waiting for the owner to upload to TikTok by "
                     "hand (auto-post is blocked — see crosspost.py). Delete an "
                     "asset here (and its tiktok_manual_queue.json entry) once "
                     "you've posted it.",
            "prerelease": True}, timeout=30)
    r.raise_for_status()
    return r.json()


def load_tiktok_queue():
    if TIKTOK_QUEUE.exists():
        return json.loads(TIKTOK_QUEUE.read_text(encoding="utf-8"))
    return {"pending": []}


def save_tiktok_queue(q):
    TIKTOK_QUEUE.write_text(json.dumps(q, indent=2, ensure_ascii=False), encoding="utf-8")


def stage_for_tiktok(video: Path, caption):
    """Upload the same captioned mp4 IG/FB post to an accumulating Release
    (never pruned — a queue, not a one-shot stage) and record it so the owner
    can browse tiktok_manual_queue.json for what's left to upload by hand."""
    if not (GH_TOKEN and GH_REPO):
        raise RuntimeError("GITHUB_TOKEN / GITHUB_REPOSITORY needed to stage for TikTok")
    api = f"https://api.github.com/repos/{GH_REPO}"
    h = {"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json"}
    release = _get_or_create_tiktok_release(api, h)
    up = release["upload_url"].split("{")[0]
    with open(video, "rb") as f:
        r = requests.post(f"{up}?name={video.name}",
                          headers={**h, "Content-Type": "video/mp4"},
                          data=f, timeout=600)
    r.raise_for_status()
    url = r.json()["browser_download_url"]
    q = load_tiktok_queue()
    q["pending"].append({
        "slug": video.stem, "url": url, "caption": caption,
        "staged": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    save_tiktok_queue(q)
    return url


def main():
    do_ig = "ig" in TARGETS and TOKEN and IG_USER_ID
    do_fb = "fb" in TARGETS and TOKEN and FB_PAGE_ID
    # "tt" now means "stage a copy for manual upload", not auto-post (API
    # rejected 2026-07-22) — only needs the GitHub token everything else here
    # already requires, no TikTok creds.
    do_tt = "tt" in TARGETS and GH_TOKEN and GH_REPO
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
    def _try(name, fn, attempts=3, backoff=15):
        """Post to one platform, retrying transient failures. IG in particular
        returns a container 'ERROR' status that is usually a transient media-
        processing blip (2026-07-20: the same mp4 posted fine to FB + TikTok
        while IG's container errored once). Each platform's post function RAISES
        before its content is published on the common failure paths (IG errors
        pre-publish; FB/TikTok raise at start/upload/finish), so re-calling it
        creates a fresh attempt without double-posting. Returns 'ok:<id>' or
        'fail:<last error>'."""
        last = None
        for i in range(attempts):
            try:
                return f"ok:{fn()}"
            except Exception as e:
                last = e
                log(f"{name} attempt {i + 1}/{attempts} failed: {e}")
                if i + 1 < attempts:
                    time.sleep(backoff * (i + 1))
        return f"fail:{last}"
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
        results["ig"] = _try("instagram", lambda: post_instagram(public_url, caption))
        log("instagram:", results["ig"])
    if do_fb:
        results["fb"] = _try("facebook", lambda: post_facebook(public_url, caption))
        log("facebook:", results["fb"])
    if do_tt:
        results["tt"] = _try("tiktok-stage", lambda: stage_for_tiktok(video, caption))
        log("tiktok (manual queue):", results["tt"])

    write_telemetry(video, results)

    # Surface a persistent failure: the crosspost step is continue-on-error so
    # a silent fail used to leave the run green with nobody the wiser
    # (2026-07-20 IG miss). Exit non-zero when a target we attempted still
    # failed after retries, so the pipeline's failure alarm (watchdog reads the
    # receipt; the step stays continue-on-error so YouTube upload is unaffected)
    # can flag it.
    failed = [p for p, v in results.items() if str(v).startswith("fail")]
    if failed:
        log(f"cross-post incomplete after retries: {failed}")
        sys.exit(1)


if __name__ == "__main__":
    main()
