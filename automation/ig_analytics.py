"""Instagram Reels analytics for the Snackbyte account.

Pulls per-Reel insights via the Meta Graph API (the same META_PAGE_TOKEN the
crosspost uses) and writes a Markdown report to analytics/instagram.md, so the
owner can see IG performance without opening the app and a session can read it
from the repo (like the YouTube receipts). Read-only; posts nothing.

Env: META_PAGE_TOKEN, IG_USER_ID (both already GitHub secrets).
"""
import os
import sys
import statistics
from datetime import datetime, timezone
from pathlib import Path

import requests

GRAPH = "https://graph.facebook.com/v21.0"
TOKEN = os.environ.get("META_PAGE_TOKEN")
IG_USER_ID = os.environ.get("IG_USER_ID")
LIMIT = int(os.environ.get("IG_ANALYTICS_LIMIT", "25"))
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "analytics" / "instagram.md"

# Reels media insight metrics. Meta renames/deprecates these periodically
# (e.g. plays -> views), so we request a preferred set and, on a 400 that
# names an unsupported metric, drop it and retry - one bad metric never kills
# the whole report.
PREF_METRICS = ["reach", "views", "ig_reels_avg_watch_time",
                "ig_reels_video_view_total_count", "total_interactions",
                "saved", "shares", "likes", "comments"]


def _get(url, params):
    r = requests.get(url, params=params, timeout=30)
    return r


def fetch_media():
    """Recent Reels: id, caption, timestamp, permalink, like/comment counts."""
    url = f"{GRAPH}/{IG_USER_ID}/media"
    fields = ("id,caption,media_type,media_product_type,timestamp,permalink,"
              "like_count,comments_count")
    out = []
    params = {"fields": fields, "limit": LIMIT, "access_token": TOKEN}
    r = _get(url, params)
    if not r.ok:
        sys.exit(f"media list failed {r.status_code}: {r.text[:300]}")
    for m in r.json().get("data", []):
        if m.get("media_product_type") in ("REELS", "VIDEO", "FEED"):
            out.append(m)
    return out


def fetch_insights(media_id):
    """Insight metrics for one media, dropping any the API rejects."""
    metrics = list(PREF_METRICS)
    url = f"{GRAPH}/{media_id}/insights"
    for _ in range(len(metrics)):
        r = _get(url, {"metric": ",".join(metrics), "access_token": TOKEN})
        if r.ok:
            vals = {}
            for item in r.json().get("data", []):
                v = item.get("values", [{}])[0].get("value")
                vals[item["name"]] = v
            return vals
        body = r.text
        # drop the metric the error complains about, then retry
        dropped = None
        for m in metrics:
            if m in body and ("does not support" in body or "not available" in body
                              or "Invalid" in body or "unsupported" in body):
                dropped = m
                break
        if dropped:
            metrics.remove(dropped)
            if metrics:
                continue
        return {"_error": f"{r.status_code}: {body[:150]}"}
    return {}


def caption_title(cap):
    if not cap:
        return "(no caption)"
    return cap.strip().splitlines()[0][:60]


def main():
    if not (TOKEN and IG_USER_ID):
        sys.exit("META_PAGE_TOKEN and IG_USER_ID must be set")
    media = fetch_media()
    rows = []
    for m in media:
        ins = fetch_insights(m["id"])
        reach = ins.get("reach")
        views = ins.get("views") or ins.get("ig_reels_video_view_total_count")
        awt = ins.get("ig_reels_avg_watch_time")     # milliseconds
        awt_s = round(awt / 1000, 1) if isinstance(awt, (int, float)) else None
        rows.append({
            "date": (m.get("timestamp") or "")[:10],
            "title": caption_title(m.get("caption")),
            "reach": reach,
            "views": views,
            "awt_s": awt_s,
            "likes": m.get("like_count"),
            "comments": m.get("comments_count"),
            "saved": ins.get("saved"),
            "shares": ins.get("shares"),
            "permalink": m.get("permalink"),
            "err": ins.get("_error"),
        })

    def num(x):
        return x if isinstance(x, (int, float)) else 0

    reaches = [num(r["reach"]) for r in rows if r["reach"] is not None]
    awts = [r["awt_s"] for r in rows if isinstance(r["awt_s"], (int, float))]
    likes = [num(r["likes"]) for r in rows if r["likes"] is not None]
    # A permission/metric error that hits (almost) every media is one problem,
    # not 25 - collapse it so the report reads clean and names the fix.
    err_rows = [r for r in rows if r["err"]]
    perm_blocked = sum(1 for r in err_rows if "permission" in (r["err"] or "").lower()
                       or '"code":10' in (r["err"] or ""))

    lines = [f"# Instagram Reels analytics ({datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC)",
             "",
             f"Account IG user {IG_USER_ID}. Last {len(rows)} media via Graph API.",
             "",
             "avg_watch_time is IG's retention signal (higher = fewer scroll-aways). "
             "IG's API gives no direct skip-rate; low avg watch time relative to the "
             "Reel length is the skip proxy.",
             "",
             "| Date | Reach | Views | AvgWatch s | Likes | Cmt | Saved | Shares | Title |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        awt = r["awt_s"] if r["awt_s"] is not None else "-"
        lines.append("| {date} | {reach} | {views} | {awt} | {likes} | {comments} "
                     "| {saved} | {shares} | {title} |".format(
                         awt=awt,
                         **{k: ("-" if r[k] is None else r[k]) for k in
                            ("date", "reach", "views", "likes", "comments",
                             "saved", "shares", "title")}))
    lines += ["",
              "## Summary",
              f"- Media: {len(rows)}",
              f"- Median reach: {int(statistics.median(reaches)) if reaches else 'n/a'}",
              f"- Max reach: {int(max(reaches)) if reaches else 'n/a'}",
              f"- Median avg watch time: {round(statistics.median(awts), 1) if awts else 'n/a'}s",
              f"- Likes (median / max): {int(statistics.median(likes)) if likes else 'n/a'} / "
              f"{int(max(likes)) if likes else 'n/a'}",
              ""]
    if perm_blocked >= max(1, len(rows) // 2):
        lines += [
            "## Insights blocked - token needs `instagram_manage_insights`",
            f"Reach / views / watch-time came back empty for {perm_blocked}/{len(rows)} "
            "media with `(#10) Application does not have permission`. The Meta token "
            "has posting scopes but not insight-read. Re-mint META_PAGE_TOKEN with "
            "`instagram_manage_insights` (plus `instagram_basic`, `pages_read_engagement`) "
            "added, update the secret, and re-run - likes/comments above already work "
            "without it.", ""]
    else:
        other = [r for r in err_rows if not ("permission" in (r["err"] or "").lower()
                                              or '"code":10' in (r["err"] or ""))]
        if other:
            lines += ["## Insight errors",
                      *[f"- {r['date']} {r['title']}: {r['err']}" for r in other], ""]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(rows)} media)")
    print("\n".join(lines[:14]))


if __name__ == "__main__":
    main()
