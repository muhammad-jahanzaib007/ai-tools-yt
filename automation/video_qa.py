#!/usr/bin/env python3
"""Look at the rendered video and say whether it is fit to publish.

Why (2026-09-21): every insight video from 2026-07-24 to 2026-09-21 opened on
a blank gradient over live narration. Nothing caught it because nothing in the
pipeline ever inspected a FRAME. blackdetect could not see it (the background
is a dark gradient, not black), the receipts said 8/8 keyword images staged,
and the analytics table said retention was fine. All true, all blind.

The check is deliberately crude and self-calibrating: sample a frame a second,
take the compressed size of each as a proxy for how much is on screen, and
compare against this video's OWN median. A caption plus two photo cards is
several times the bytes of an empty gradient, so a frame far below the video's
own middle is a frame with nothing on it. Comparing a video to itself means a
legitimately sparse style cannot trip the check, and no absolute threshold has
to be maintained.

Two failures, both "the screen is empty when it should not be":
  * a blank OPENING, the expensive one, since the first seconds decide whether
    a Short is watched at all
  * any empty SPAN long enough to read as a glitch mid-video

Exit code 1 under --gate means do not publish this render. publish.yml re-renders
and checks again rather than giving up: TTS and Whisper are non-deterministic,
so a fresh take usually lands clean.

Usage:
    python automation/video_qa.py [path.mp4] [--gate] [--json out.json]
"""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# A frame under this fraction of the video's own median detail is "empty".
EMPTY_RATIO = 0.35
# An empty stretch at least this long mid-video reads as a glitch.
MIN_SPAN_S = 2.0
# The opening window that decides whether a Short is watched. Starts after the
# hook card's own fade so a legitimate fade-out is not counted as emptiness.
OPEN_FROM, OPEN_TO = 1.0, 4.0


def duration(path):
    p = subprocess.run(["ffmpeg", "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", p.stderr)
    if not m:
        return None
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def frame_profile(path, fps=1):
    """[(t_seconds, jpeg_bytes)] sampled at `fps`, in one ffmpeg pass."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        r = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path),
             "-vf", f"fps={fps},scale=240:-1", "-q:v", "6",
             str(td / "f%04d.jpg")],
            capture_output=True, text=True)
        files = sorted(td.glob("f*.jpg"))
        if not files:
            print(f"video_qa: no frames extracted ({r.stderr[-200:]})", file=sys.stderr)
            return []
        # ffmpeg's fps filter emits the first frame at t=0, then every 1/fps.
        return [((i / fps), f.stat().st_size) for i, f in enumerate(files)]


def analyse(profile):
    """(ok, reasons, stats) from a frame profile."""
    if not profile:
        return True, [], {}          # cannot judge: do not block on a read failure
    sizes = sorted(s for _, s in profile)
    median = sizes[len(sizes) // 2] or 1
    floor = EMPTY_RATIO * median
    reasons = []

    opening = [s for t, s in profile if OPEN_FROM <= t <= OPEN_TO]
    open_ratio = (sum(opening) / len(opening) / median) if opening else 1.0
    if opening and open_ratio < EMPTY_RATIO:
        reasons.append(
            f"blank opening: {OPEN_FROM:.0f}-{OPEN_TO:.0f}s averages "
            f"{open_ratio:.0%} of this video's own median detail")

    # longest empty run anywhere
    longest, run_start, prev_t = 0.0, None, None
    for t, s in profile:
        if s < floor:
            if run_start is None:
                run_start = t
            longest = max(longest, t - run_start)
        else:
            run_start = None
        prev_t = t
    if longest >= MIN_SPAN_S:
        reasons.append(f"empty stretch of {longest:.0f}s where nothing is on screen")

    stats = {"median_bytes": median, "open_ratio": round(open_ratio, 3),
             "longest_empty_s": round(longest, 1), "frames": len(profile)}
    return (not reasons), reasons, stats


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    gate = "--gate" in sys.argv
    if args:
        video = Path(args[0])
    else:
        vids = sorted((ROOT / "output").glob("*.mp4"), key=lambda p: p.stat().st_mtime)
        if not vids:
            print("video_qa: no rendered video found", file=sys.stderr)
            return 0
        video = vids[-1]

    profile = frame_profile(video)
    ok, reasons, stats = analyse(profile)

    dur = duration(video)
    print(f"video_qa: {video.name} {dur:.1f}s {stats}" if dur else f"video_qa: {video.name} {stats}")
    if profile:
        median = stats["median_bytes"]
        for t, s in profile:
            if t <= 8 or s < EMPTY_RATIO * median:      # opening, plus anything empty
                bar = "#" * max(1, int(20 * s / median))
                flag = "  <-- empty" if s < EMPTY_RATIO * median else ""
                print(f"  {t:5.1f}s {s:7d}B {bar}{flag}")

    if "--json" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--json") + 1])
        out.write_text(json.dumps({"ok": ok, "reasons": reasons, "stats": stats},
                                  indent=2), encoding="utf-8")

    if reasons:
        for r in reasons:
            print(f"video_qa: FAIL - {r}")
        if gate:
            return 1
    else:
        print("video_qa: PASS - the frame is populated throughout")
    return 0


if __name__ == "__main__":
    sys.exit(main())
