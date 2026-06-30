#!/usr/bin/env python3
"""
Phase 2: render a video from a brief.

For the chosen brief (newest in briefs/, or BRIEF_SLUG):
  1. ElevenLabs TTS for each narration segment -> mp3 clips
  2. Pexels video search + download for each segment's b-roll query
  3. ffmpeg: per-segment clip (b-roll scaled/cropped to 1080x1920, looped to the
     narration length) -> concat -> burn captions (SRT) -> optional background music
  4. Output output/<slug>.mp4 (+ output/<slug>.jpg thumbnail) for the Actions artifact

Requires ffmpeg/ffprobe on PATH and these env vars:
  ELEVENLABS_API_KEY, PEXELS_API_KEY  (required)
  VOICE_ID            (default Rachel: 21m00Tcm4TlvDq8ikWAM)
  ELEVEN_MODEL        (default eleven_turbo_v2_5)
  BRIEF_SLUG          (optional: render a specific brief)
Optional background music: place a royalty-free track at assets/music.mp3.
"""

import os
import re
import sys
import json
import math
import shutil
import subprocess
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
BRIEFS = ROOT / "briefs"
OUT = ROOT / "output"
WORK = ROOT / ".render"
MUSIC = ROOT / "assets" / "music.mp3"

EL_KEY = os.environ.get("ELEVENLABS_API_KEY")
PX_KEY = os.environ.get("PEXELS_API_KEY")
VOICE_ID = os.environ.get("VOICE_ID") or "21m00Tcm4TlvDq8ikWAM"      # Rachel
EL_MODEL = os.environ.get("ELEVEN_MODEL") or "eleven_multilingual_v2"
W, H, FPS = 1080, 1920, 30


def run(cmd, cwd=None):
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if p.returncode != 0:
        sys.exit(f"command failed: {' '.join(cmd[:6])}...\n{p.stderr[-1500:]}")
    return p.stdout


def probe_duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(path)])
    return float(out.strip())


def pick_brief():
    if not BRIEFS.exists():
        sys.exit("no briefs/ directory")
    files = list(BRIEFS.glob("*.json"))
    if not files:
        sys.exit("no briefs found")
    slug = os.environ.get("BRIEF_SLUG")
    if slug:
        f = BRIEFS / f"{slug}.json"
        if not f.exists():
            sys.exit(f"brief not found: {slug}")
        return json.loads(f.read_text(encoding="utf-8"))
    best = max(files, key=lambda f: (json.loads(f.read_text(encoding="utf-8")).get("date", ""), f.name))
    return json.loads(best.read_text(encoding="utf-8"))


def tts(text, dest):
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
        params={"output_format": "mp3_44100_128"},
        headers={"xi-api-key": EL_KEY, "Content-Type": "application/json"},
        json={"text": text, "model_id": EL_MODEL,
              "voice_settings": {"stability": 0.4, "similarity_boost": 0.85,
                                 "style": 0.25, "use_speaker_boost": True}},
        timeout=120,
    )
    if r.status_code >= 400:
        sys.exit(f"ElevenLabs failed ({r.status_code}): {r.text[:400]}")
    dest.write_bytes(r.content)


def pexels_clip(query, dest):
    for q in (query, "abstract technology background", "digital network motion"):
        try:
            r = requests.get(
                "https://api.pexels.com/videos/search",
                params={"query": q, "per_page": 10, "orientation": "portrait", "size": "medium"},
                headers={"Authorization": PX_KEY}, timeout=60,
            )
            if r.status_code >= 400:
                continue
            vids = r.json().get("videos", [])
        except requests.RequestException:
            continue
        for v in vids:
            mp4s = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("height")]
            if not mp4s:
                continue
            tall = [f for f in mp4s if f["height"] >= f.get("width", 0)] or mp4s   # prefer vertical
            f = min(tall, key=lambda x: abs(x["height"] - 1280))
            try:
                with requests.get(f["link"], stream=True, timeout=180) as dl:
                    if dl.status_code >= 400:
                        continue
                    with open(dest, "wb") as fh:
                        for chunk in dl.iter_content(1 << 16):
                            fh.write(chunk)
                if dest.stat().st_size > 10000:
                    return True
            except requests.RequestException:
                continue
    return False


def make_segment(idx, audio, broll, dur, dest):
    if broll and broll.exists():
        # Ken Burns: gentle continuous zoom, alternating in/out per segment so nothing is static
        z = "min(1+0.0011*on,1.22)" if idx % 2 == 0 else "max(1.22-0.0011*on,1.0)"
        vf = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
              f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS},"
              f"format=yuv420p[v]")
        run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(broll), "-i", str(audio), "-t", f"{dur:.3f}",
             "-filter_complex", vf,
             "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast",
             "-c:a", "aac", "-ar", "44100", "-shortest", str(dest)])
    else:
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x0b0b14:s={W}x{H}:r={FPS}",
             "-i", str(audio), "-t", f"{dur:.3f}", "-pix_fmt", "yuv420p",
             "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-ar", "44100",
             "-shortest", str(dest)])


def build_ass(segs, durations, path):
    """Lower-third captions, sized in real 1080x1920 pixels, split per sentence."""
    header = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n"
        "WrapStyle: 0\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, "
        "Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Cap,DejaVu Sans,60,&H00FFFFFF,&H000000FF,&H0000C8FF,&H64000000,-1,0,0,0,"
        "100,100,0,0,1,6,2,2,90,90,330,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    # pop-in: quick fade + scale bounce so each caption grabs the eye
    pop = r"{\fad(80,50)\fscx72\fscy72\t(0,130,\fscx107\fscy107)\t(130,230,\fscx100\fscy100)}"

    def ts(t):
        cs = int(round(t * 100)); h, cs = divmod(cs, 360000); m, cs = divmod(cs, 6000); s, cs = divmod(cs, 100)
        return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"

    lines, t0 = [], 0.0
    for seg, d in zip(segs, durations):
        text = " ".join(seg["text"].split())
        parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()] or [text]
        tot = sum(len(p) for p in parts) or 1
        st = t0
        for j, p in enumerate(parts):
            en = (t0 + d) if j == len(parts) - 1 else st + d * len(p) / tot
            safe = pop + p.replace("{", "(").replace("}", ")")
            lines.append(f"Dialogue: 0,{ts(st)},{ts(en)},Cap,,0,0,0,,{safe}")
            st = en
        t0 += d
    path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")


def main():
    if not EL_KEY or not PX_KEY:
        sys.exit("ELEVENLABS_API_KEY and PEXELS_API_KEY must be set")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        sys.exit("ffmpeg/ffprobe not found on PATH")

    brief = pick_brief()
    slug = brief["slug"]
    segs = brief["narration"]
    print(f"Rendering: {brief['title']}  ({len(segs)} segments)")

    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    OUT.mkdir(exist_ok=True)

    durations, seg_files = [], []
    for i, seg in enumerate(segs):
        audio = WORK / f"a{i}.mp3"
        tts(seg["text"], audio)
        d = probe_duration(audio) + 0.35           # small tail so captions/cuts don't clip
        broll = WORK / f"b{i}.mp4"
        if not pexels_clip(seg.get("broll", brief["title"]), broll):
            broll = None
        seg_mp4 = WORK / f"s{i}.mp4"
        make_segment(i, audio, broll, d, seg_mp4)
        durations.append(d); seg_files.append(seg_mp4)
        print(f"  segment {i+1}/{len(segs)} ok ({d:.1f}s)")

    # concat
    listf = WORK / "list.txt"
    listf.write_text("".join(f"file '{f.as_posix()}'\n" for f in seg_files), encoding="utf-8")
    body = WORK / "body.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listf), "-c", "copy", str(body)])

    # captions (ASS) + optional music -> final.  Run from WORK so subtitles=subs.ass is a simple path.
    build_ass(segs, durations, WORK / "subs.ass")
    final = OUT / f"{slug}.mp4"
    if MUSIC.exists():
        run(["ffmpeg", "-y", "-i", "body.mp4", "-stream_loop", "-1", "-i", str(MUSIC.resolve()),
             "-filter_complex",
             "[0:v]subtitles=subs.ass[v];[1:a]volume=0.07[m];[0:a][m]amix=inputs=2:duration=first[a]",
             "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "21",
             "-c:a", "aac", "-ar", "44100", "-shortest", str(final.resolve())], cwd=str(WORK))
    else:
        run(["ffmpeg", "-y", "-i", "body.mp4", "-vf", "subtitles=subs.ass",
             "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-c:a", "copy",
             str(final.resolve())], cwd=str(WORK))

    # thumbnail: frame + big title text
    thumb = OUT / f"{slug}.jpg"
    ttext = brief.get("thumbnail_text", "").replace(":", r"\:").replace("'", "")
    p = subprocess.run(
        ["ffmpeg", "-y", "-i", str(final.resolve()), "-vf",
         f"select=eq(n\\,30),scale={W}:{H},"
         f"drawbox=y=ih*0.40:color=black@0.45:width=iw:height=ih*0.2:t=fill,"
         f"drawtext=font='DejaVu Sans':text='{ttext}':fontcolor=white:fontsize=90:"
         f"x=(w-text_w)/2:y=(h-text_h)/2:box=0",
         "-frames:v", "1", str(thumb.resolve())],
        capture_output=True, text=True)
    if p.returncode != 0:
        print("thumbnail step skipped:", p.stderr[-300:], file=sys.stderr)

    dur = probe_duration(final)
    print(f"DONE: {final.relative_to(ROOT)}  ({dur:.1f}s, {final.stat().st_size//1024} KB)")


if __name__ == "__main__":
    main()
