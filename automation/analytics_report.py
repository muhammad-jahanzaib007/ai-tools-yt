#!/usr/bin/env python3
"""
Phase 4a: weekly channel analytics report via the YouTube Analytics API.

Writes analytics/report-<date>.md with channel totals (last 28 days) and a
per-video table (views, watch time, avg view %, likes, subs gained) so topic
selection can learn from what actually retains viewers.

Required env (repo secrets):
  YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN

IMPORTANT: the refresh token must be minted with these scopes (the original
upload-only token will fail with 403 insufficientPermissions):
  https://www.googleapis.com/auth/youtube.upload
  https://www.googleapis.com/auth/youtube.readonly
  https://www.googleapis.com/auth/yt-analytics.readonly
Re-mint via https://developers.google.com/oauthplayground with your own
client ID/secret (gear icon > "Use your own OAuth credentials"), authorize the
three scopes above, exchange for a refresh token, then update the
YT_REFRESH_TOKEN repo secret.
"""

import os
import sys
import datetime as dt
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "analytics"

CID = os.environ.get("YT_CLIENT_ID")
CSEC = os.environ.get("YT_CLIENT_SECRET")
RT = os.environ.get("YT_REFRESH_TOKEN")

SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def main():
    if not (CID and CSEC and RT):
        sys.exit("YT_CLIENT_ID, YT_CLIENT_SECRET and YT_REFRESH_TOKEN must be set")

    creds = Credentials(
        None, refresh_token=RT, client_id=CID, client_secret=CSEC,
        token_uri="https://oauth2.googleapis.com/token", scopes=SCOPES,
    )
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    yta = build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)

    end = dt.date.today() - dt.timedelta(days=1)
    start = end - dt.timedelta(days=27)
    s, e = start.isoformat(), end.isoformat()

    # Channel totals for the window.
    totals = yta.reports().query(
        ids="channel==MINE", startDate=s, endDate=e,
        metrics="views,estimatedMinutesWatched,averageViewDuration,"
                "subscribersGained,subscribersLost,likes,comments",
    ).execute()
    trow = (totals.get("rows") or [[0] * 7])[0]

    # Top videos in the window.
    top = yta.reports().query(
        ids="channel==MINE", startDate=s, endDate=e,
        metrics="views,estimatedMinutesWatched,averageViewPercentage,"
                "likes,comments,subscribersGained",
        dimensions="video", sort="-views", maxResults=25,
    ).execute()
    rows = top.get("rows") or []

    # Resolve video titles via the Data API.
    titles = {}
    ids = [r[0] for r in rows]
    for i in range(0, len(ids), 50):
        resp = yt.videos().list(part="snippet", id=",".join(ids[i:i + 50])).execute()
        for v in resp.get("items", []):
            titles[v["id"]] = v["snippet"]["title"]

    lines = [
        f"# Channel analytics: {s} to {e}",
        "",
        "## Totals (28 days)",
        "",
        f"- Views: {trow[0]}",
        f"- Watch time: {trow[1]} min",
        f"- Avg view duration: {trow[2]} s",
        f"- Subscribers: +{trow[3]} / -{trow[4]}",
        f"- Likes: {trow[5]}  Comments: {trow[6]}",
        "",
        "## Videos by views",
        "",
        "| Video | Views | Watch min | Avg view % | Likes | Comments | Subs |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        vid, views, mins, avgpct, likes, comments, subs = r[:7]
        title = titles.get(vid, vid).replace("|", "-")
        lines.append(
            f"| [{title}](https://youtu.be/{vid}) | {views} | {mins} "
            f"| {avgpct:.1f} | {likes} | {comments} | {subs} |"
        )
    if not rows:
        lines.append("| (no video data in window) | | | | | | |")

    lines += [
        "",
        "_Avg view % under ~50 on a Short usually means the hook or pacing is "
        "losing people; compare formats, not just totals._",
        "",
    ]

    # YouTube Analytics lags ~2-3 days; a young channel's first reports come
    # back empty. Say so, or an all-zero report reads like channel death.
    if not rows and not any(trow):
        lines[2:2] = [
            "> **Data note:** the Analytics API lags ~2-3 days. An all-zero "
            "report on a young channel means the data has not landed yet, "
            "not zero performance.",
            "",
        ]

    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / f"report-{end.isoformat()}.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    (OUT_DIR / "latest.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out.relative_to(ROOT)} ({len(rows)} videos)")


if __name__ == "__main__":
    main()
