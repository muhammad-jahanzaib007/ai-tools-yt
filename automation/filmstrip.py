#!/usr/bin/env python3
"""Tile a rendered video into ONE contact-sheet image, so it can be eyeballed.

Why (2026-09-21): every insight video since the format launched on 2026-07-24
opened on a blank gradient over live narration, and it survived months of
telemetry because nothing in the pipeline ever LOOKED at a frame. Receipts said
`8/8 keyword images staged`, audio QA said `black=none`, the analytics table
said retention was fine. All true, all blind to a video that showed nothing for
its first five seconds.

Claude can read an image but cannot play a video or hear audio. A contact sheet
turns "watch the video" into one image, which makes a visual regression as easy
to catch as a failing test. Frames are sampled densely at the START, because
that is both where the fault lived and where a Short is won or lost.

Writes <out>/<slug>-strip.jpg plus a per-frame detail profile on stdout.

Usage:
    python automation/filmstrip.py output/my-video.mp4 [--out review]
"""

import subprocess
import sys
import re
import tempfile
from pathlib import Path

# Dense early, sparse later: the first 3 seconds decide whether a Short is
# watched, and a timing fault shows up there first.
EARLY = [0.3, 0.8, 1.3, 2.0, 3.0, 4.0, 5.0, 6.0]
LATER_FRACTIONS = [0.30, 0.45, 0.60, 0.75, 0.88, 0.97]
COLS = 5


def duration(path):
    p = subprocess.run(["ffmpeg", "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", p.stderr)
    if not m:
        return None
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def grab(path, t, dest):
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(path),
         "-frames:v", "1", "-q:v", "4", "-vf", "scale=360:-1", str(dest)],
        capture_output=True, text=True)
    return dest.exists() and r.returncode == 0


def build(video, out_dir):
    video = Path(video)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dur = duration(video)
    if not dur:
        sys.exit(f"could not read duration of {video}")

    times = [t for t in EARLY if t < dur] + [round(dur * f, 2) for f in LATER_FRACTIONS]
    times = sorted(set(t for t in times if t < dur))

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        kept, profile = [], []
        for i, t in enumerate(times):
            f = td / f"f{i:02d}.jpg"
            if grab(video, t, f):
                kept.append(f)
                profile.append((t, f.stat().st_size))

        if not kept:
            sys.exit("no frames could be extracted")

        # Detail profile: byte size tracks how much is ON the frame. A near-flat
        # opening against a rich middle is the blank-opening signature.
        mid = sorted(s for _, s in profile)[len(profile) // 2] or 1
        print(f"{video.name}  {dur:.1f}s  {len(kept)} frames")
        for t, size in profile:
            bar = "#" * max(1, int(20 * size / mid))
            flag = "  <-- near-empty" if size < 0.35 * mid else ""
            print(f"  {t:5.1f}s {size:7d}B {bar}{flag}")

        rows = (len(kept) + COLS - 1) // COLS
        strip = out_dir / f"{video.stem}-strip.jpg"
        inputs = []
        for f in kept:
            inputs += ["-i", str(f)]
        # tile= needs a full grid; pad the last row with copies of the final
        # frame so ffmpeg does not error on a short input list.
        while len(inputs) // 2 < rows * COLS:
            inputs += ["-i", str(kept[-1])]
        n = len(inputs) // 2
        filt = "".join(f"[{i}:v]" for i in range(n)) + \
               f"xstack=inputs={n}:layout=" + \
               "|".join(f"{(i % COLS)}_{(i // COLS)}" for i in range(n)) + "[v]"
        # xstack layout wants pixel offsets on modern ffmpeg; tile is simpler
        # and available everywhere we run.
        filt = f"tile={COLS}x{rows}:margin=6:padding=4:color=#202024"
        r = subprocess.run(
            ["ffmpeg", "-v", "error", "-y"] + sum([["-i", str(f)] for f in kept], []) +
            ["-filter_complex",
             "".join(f"[{i}:v]" for i in range(len(kept))) +
             f"concat=n={len(kept)}:v=1:a=0,{filt}[v]",
             "-map", "[v]", "-q:v", "3", str(strip)],
            capture_output=True, text=True)
        if r.returncode != 0 or not strip.exists():
            sys.exit(f"tile failed: {r.stderr[-400:]}")
        print(f"strip: {strip} ({strip.stat().st_size // 1024}KB)")
        return strip


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = "review"
    if "--out" in sys.argv:
        out = sys.argv[sys.argv.index("--out") + 1]
    if not args:
        sys.exit(__doc__)
    build(args[0], out)
