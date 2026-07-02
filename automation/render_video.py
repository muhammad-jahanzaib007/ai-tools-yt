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
import base64
import random
import shutil
import subprocess
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
BRIEFS = ROOT / "briefs"
OUT = ROOT / "output"
WORK = ROOT / ".render"
MUSIC_DIR = ROOT / "assets" / "music"          # drop several .mp3 here -> a random one per video
MUSIC_FILE = ROOT / "assets" / "music.mp3"     # or a single track as fallback
REMOTION_DIR = ROOT / "remotion"
TRANS = 15                                     # = TRANSITION_FRAMES in remotion/src/battle/types.ts
NPX = "npx.cmd" if os.name == "nt" else "npx"


def pick_music(vibe="battle"):
    if MUSIC_DIR.is_dir():
        # manifest.json tags tracks by measured BPM/energy; battles get only
        # high-tempo punchy tracks so the music matches the format
        manifest = MUSIC_DIR / "manifest.json"
        if manifest.exists():
            try:
                entries = json.loads(manifest.read_text(encoding="utf-8"))["tracks"]
                pool = [MUSIC_DIR / t["file"] for t in entries
                        if t.get("vibe") == vibe and (MUSIC_DIR / t["file"]).exists()]
                if pool:
                    return random.choice(pool)
            except Exception as e:
                print(f"music manifest ignored: {e}", file=sys.stderr)
        tracks = sorted(MUSIC_DIR.glob("*.mp3")) + sorted(MUSIC_DIR.glob("*.m4a"))
        if tracks:
            return random.choice(tracks)
    return MUSIC_FILE if MUSIC_FILE.exists() else None

EL_KEY = os.environ.get("ELEVENLABS_API_KEY")
PX_KEY = os.environ.get("PEXELS_API_KEY")
VOICE_ID = os.environ.get("VOICE_ID") or "Fahco4VZzobUeiPqni1S"      # user-picked library voice
EL_MODEL = os.environ.get("ELEVEN_MODEL") or "eleven_multilingual_v2"
# Expressive delivery: low stability = more variation between sentences, high
# style = more emotion. The old 0.4/0.25 sounded like reading from a book.
VOICE_SETTINGS = {
    "stability": float(os.environ.get("VOICE_STABILITY", "0.30")),
    "similarity_boost": float(os.environ.get("VOICE_SIMILARITY", "0.75")),
    "style": float(os.environ.get("VOICE_STYLE", "0.55")),
    "use_speaker_boost": True,
    "speed": float(os.environ.get("VOICE_SPEED", "1.09")),
}
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
    if not slug:
        latest = ROOT / "automation" / "latest.txt"      # written by generate_brief
        if latest.exists():
            slug = latest.read_text(encoding="utf-8").strip()
    if slug:
        f = BRIEFS / f"{slug}.json"
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
    best = max(files, key=lambda f: f.stat().st_mtime)    # fallback: newest file on disk
    return json.loads(best.read_text(encoding="utf-8"))


def tts(text, dest):
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
        params={"output_format": "mp3_44100_128"},
        headers={"xi-api-key": EL_KEY, "Content-Type": "application/json"},
        json={"text": text, "model_id": EL_MODEL, "voice_settings": VOICE_SETTINGS},
        timeout=120,
    )
    if r.status_code >= 400:
        sys.exit(f"ElevenLabs failed ({r.status_code}): {r.text[:400]}")
    dest.write_bytes(r.content)


def tts_timed(text, dest):
    """TTS with word timings. Returns [(word, start_s, end_s)] or raises if unavailable."""
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/with-timestamps",
        params={"output_format": "mp3_44100_128"},
        headers={"xi-api-key": EL_KEY, "Content-Type": "application/json"},
        json={"text": text, "model_id": EL_MODEL, "voice_settings": VOICE_SETTINGS},
        timeout=120,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"with-timestamps {r.status_code}: {r.text[:200]}")
    j = r.json()
    dest.write_bytes(base64.b64decode(j["audio_base64"]))
    al = j.get("alignment") or j.get("normalized_alignment")
    chars = al["characters"]
    st = al["character_start_times_seconds"]
    en = al["character_end_times_seconds"]
    words, cur, cs, ce = [], "", None, None
    for c, s, e in zip(chars, st, en):
        if c.isspace():
            if cur:
                words.append((cur, cs, ce)); cur, cs = "", None
        else:
            if not cur:
                cs = s
            cur += c; ce = e
    if cur:
        words.append((cur, cs, ce))
    return words


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


def _ass_header(primary, secondary):
    return (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n"
        "WrapStyle: 0\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, "
        "Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Cap,DejaVu Sans,64,{primary},{secondary},&H00000000,&H64000000,-1,0,0,0,"
        "100,100,0,0,1,6,2,2,90,90,360,1\n"
        "Style: Hook,DejaVu Sans,80,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,"
        "100,100,0,0,1,7,2,8,120,120,360,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )


def _hook_line(title):
    if not title:
        return None
    safe = title.replace("{", "(").replace("}", ")")
    return f"Dialogue: 0,0:00:00.00,0:00:02.40,Hook,,0,0,0,,{{\\fad(150,180)}}{safe}"


def _ts(t):
    cs = int(round(t * 100)); h, cs = divmod(cs, 360000); m, cs = divmod(cs, 6000); s, cs = divmod(cs, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def build_karaoke_ass(words, path, group=4, title=None):
    """Word-by-word highlight: unsung white, active word pops to yellow, in sync with speech."""
    header = _ass_header("&H0000FFFF", "&H00FFFFFF")     # PrimaryColour=yellow (sung), Secondary=white
    lines = []
    hook = _hook_line(title)
    if hook:
        lines.append(hook)
    for k in range(0, len(words), group):
        chunk = words[k:k + group]
        start, end = chunk[0][1], chunk[-1][2]
        parts = []
        for i, (w, s, e) in enumerate(chunk):
            nxt = chunk[i + 1][1] if i + 1 < len(chunk) else e
            kcs = max(1, int(round((nxt - s) * 100)))
            safe = w.replace("{", "(").replace("}", ")")
            parts.append(f"{{\\k{kcs}}}{safe} ")
        text = r"{\fad(60,40)}" + "".join(parts).strip()
        lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Cap,,0,0,0,,{text}")
    path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")


def make_segment(idx, audio, broll, dur, dest):
    if broll and broll.exists():
        # Ken Burns: continuous zoom using the accumulating `zoom` var (NOT `on`, which is static).
        # Oversize first so zooming doesn't upscale past source.
        # Alternate zoom direction per segment so every cut lands with a visible motion change.
        if idx % 2 == 0:
            zexpr = "min(zoom+0.0032,1.35)"
        else:
            zexpr = "if(lte(zoom,1.0),1.35,max(zoom-0.0032,1.001))"
        vf = (f"[0:v]scale={int(W*1.4)}:{int(H*1.4)}:force_original_aspect_ratio=increase,"
              f"crop={int(W*1.4)}:{int(H*1.4)},"
              f"zoompan=z='{zexpr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
              f"d=1:s={W}x{H}:fps={FPS},format=yuv420p[v]")
        run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(broll), "-i", str(audio), "-t", f"{dur:.3f}",
             "-filter_complex", vf,
             "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast",
             "-c:a", "aac", "-ar", "44100", "-shortest", str(dest)])
    else:
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x0b0b14:s={W}x{H}:r={FPS}",
             "-i", str(audio), "-t", f"{dur:.3f}", "-pix_fmt", "yuv420p",
             "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-ar", "44100",
             "-shortest", str(dest)])


def build_ass(segs, durations, path, title=None):
    """Lower-third captions, sized in real 1080x1920 pixels, split per sentence."""
    header = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n"
        "WrapStyle: 0\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, "
        "Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Cap,DejaVu Sans,60,&H00FFFFFF,&H000000FF,&H0000C8FF,&H64000000,-1,0,0,0,"
        "100,100,0,0,1,6,2,2,90,90,330,1\n"
        "Style: Hook,DejaVu Sans,80,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,"
        "100,100,0,0,1,7,2,8,120,120,360,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    # pop-in: quick fade + scale bounce so each caption grabs the eye
    pop = r"{\fad(80,50)\fscx72\fscy72\t(0,130,\fscx107\fscy107)\t(130,230,\fscx100\fscy100)}"

    def ts(t):
        cs = int(round(t * 100)); h, cs = divmod(cs, 360000); m, cs = divmod(cs, 6000); s, cs = divmod(cs, 100)
        return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"

    lines, t0 = [], 0.0
    hook = _hook_line(title)
    if hook:
        lines.append(hook)
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


def make_outro(dest, seconds=1.6):
    """Branded 'Subscribe' end card (cream bg, coral wordmark) with silent audio."""
    vf = (f"drawtext=font=DejaVu Sans:text='Subscribe for daily AI tools':"
          f"fontcolor=0x1A1915:fontsize=64:x=(w-text_w)/2:y=h*0.42-40,"
          f"drawtext=font=DejaVu Sans:text='Snackbyte AI':"
          f"fontcolor=0xD97757:fontsize=80:x=(w-text_w)/2:y=h*0.42+50")
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0xF2EEE4:s={W}x{H}:r={FPS}",
         "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
         "-t", f"{seconds}", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "44100", "-shortest", str(dest)])


def _reset_work():
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    OUT.mkdir(exist_ok=True)


def build_ass_at(segs, delays, durs, path):
    """Fallback battle captions without word timings: sentences spread over
    each scene's narration window."""
    header = _ass_header("&H00FFFFFF", "&H000000FF")
    lines = []
    for seg, t0, d in zip(segs, delays, durs):
        text = " ".join(seg["text"].split())
        parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()] or [text]
        tot = sum(len(p) for p in parts) or 1
        st = t0
        for j, p in enumerate(parts):
            en = (t0 + d) if j == len(parts) - 1 else st + d * len(p) / tot
            safe = r"{\fad(80,50)}" + p.replace("{", "(").replace("}", ")")
            lines.append(f"Dialogue: 0,{_ts(st)},{_ts(en)},Cap,,0,0,0,,{safe}")
            st = en
    path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")


def render_battle(brief):
    """Battle path: TTS per scene -> Remotion motion graphics sized to the
    narration audio -> mux delayed narration + captions + music. Any failure
    raises; the caller falls back to the classic b-roll render."""
    battle = brief["battle"]
    slug = brief["slug"]
    segs = brief["narration"]        # len == rounds+2, validated at brief time
    n = len(segs)
    print(f"Battle render: {battle['toolA']} vs {battle['toolB']}  ({n} scenes)")

    # 1. narration audio per scene (+ word timings for karaoke captions)
    audios, words_per, durs, karaoke = [], [], [], True
    for i, seg in enumerate(segs):
        audio = WORK / f"a{i}.mp3"
        try:
            words_per.append(tts_timed(seg["text"], audio))
        except Exception as e:
            print(f"  word timings unavailable ({e}); plain TTS", file=sys.stderr)
            karaoke = False
            tts(seg["text"], audio)
            words_per.append([])
        audios.append(audio)
        durs.append(probe_duration(audio))
        print(f"  scene {i+1}/{n} voiced ({durs[-1]:.1f}s)")

    # 2. scene lengths: lead-in (covers the 0.5s transition) + narration + tail
    leads = [0.30 if i == 0 else 0.65 for i in range(n)]
    frames = []
    for i, d in enumerate(durs):
        tail = 2.2 if i == n - 1 else 0.8        # hold the verdict card at the end
        frames.append(int(round((leads[i] + d + tail) * FPS)))

    # absolute scene starts on the final timeline (transitions overlap by TRANS)
    starts, acc = [], 0
    for f in frames:
        starts.append(acc / FPS)
        acc += f - TRANS
    total_sec = (acc + TRANS) / FPS
    delays = [starts[i] + leads[i] for i in range(n)]

    # 3. Remotion render (silent motion graphics, duration driven by sceneFrames)
    props = dict(battle)
    props["sceneFrames"] = {"intro": frames[0], "rounds": frames[1:-1], "verdict": frames[-1]}
    props_file = WORK / "props.json"
    props_file.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    graphics = WORK / "battle.mp4"
    run([NPX, "remotion", "render", "src/index.ts", "BattleShort", str(graphics.resolve()),
         f"--props={props_file.resolve()}", "--log=error"], cwd=str(REMOTION_DIR))

    # 4. captions timed to the delayed narration
    all_words = [(w, delays[i] + s, delays[i] + e)
                 for i, ws in enumerate(words_per) for (w, s, e) in ws]
    if karaoke and all_words:
        build_karaoke_ass(all_words, WORK / "subs.ass")     # no hook overlay: VsIntro is the hook
    else:
        build_ass_at(segs, delays, durs, WORK / "subs.ass")

    # 5. mux graphics + per-scene delayed narration + music, burn captions
    inputs = ["-i", "battle.mp4"]
    filters, alabels = [], []
    for i, a in enumerate(audios):
        inputs += ["-i", str(a.resolve())]
        ms = int(round(delays[i] * 1000))
        filters.append(f"[{i+1}:a]adelay={ms}|{ms}[n{i}]")
        alabels.append(f"[n{i}]")
    music = pick_music()
    if music:
        print(f"music: {music.name}")
        inputs += ["-stream_loop", "-1", "-i", str(music.resolve())]
        filters.append(f"[{n+1}:a]volume=0.06[m]")
        alabels.append("[m]")
    filters.append("".join(alabels) + f"amix=inputs={len(alabels)}:duration=longest:normalize=0[a]")
    filters.append("[0:v]subtitles=subs.ass[v]")
    final = OUT / f"{slug}.mp4"
    run(["ffmpeg", "-y"] + inputs + [
        "-filter_complex", ";".join(filters),
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "21",
        "-c:a", "aac", "-ar", "44100",
        "-t", f"{total_sec:.3f}", str(final.resolve())], cwd=str(WORK))

    # 6. thumbnail: the VS intro frame (tool names + VS + tagline, no captions)
    thumb = OUT / f"{slug}.jpg"
    p = subprocess.run(
        ["ffmpeg", "-y", "-i", str(graphics.resolve()), "-vf",
         f"select=eq(n\\,{min(70, frames[0] - 1)})", "-frames:v", "1",
         str(thumb.resolve())], capture_output=True, text=True)
    if p.returncode != 0:
        print("thumbnail step skipped:", p.stderr[-300:], file=sys.stderr)

    dur = probe_duration(final)
    print(f"DONE (battle): {final.relative_to(ROOT)}  ({dur:.1f}s, {final.stat().st_size//1024} KB)")


def main():
    if not EL_KEY or not PX_KEY:
        sys.exit("ELEVENLABS_API_KEY and PEXELS_API_KEY must be set")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        sys.exit("ffmpeg/ffprobe not found on PATH")

    brief = pick_brief()
    slug = brief["slug"]
    segs = brief["narration"]
    print(f"Rendering: {brief['title']}  ({len(segs)} segments)")

    if brief.get("battle") and (REMOTION_DIR / "package.json").exists():
        try:
            _reset_work()
            render_battle(brief)
            return
        except KeyboardInterrupt:
            raise
        except BaseException as e:      # incl. SystemExit from run(): keep the cron alive
            print(f"battle render failed ({e}); falling back to b-roll render", file=sys.stderr)

    _reset_work()

    durations, seg_files, all_words, karaoke = [], [], [], True
    t0 = 0.0
    for i, seg in enumerate(segs):
        audio = WORK / f"a{i}.mp3"
        words = []
        try:
            words = tts_timed(seg["text"], audio)        # natural voice + word timings
        except Exception as e:
            print(f"  word timings unavailable ({e}); plain TTS for this segment", file=sys.stderr)
            karaoke = False
            tts(seg["text"], audio)
        d = probe_duration(audio) + 0.12           # small tail so captions/cuts don't clip
        broll = WORK / f"b{i}.mp4"
        if not pexels_clip(seg.get("broll", brief["title"]), broll):
            broll = None
        seg_mp4 = WORK / f"s{i}.mp4"
        make_segment(i, audio, broll, d, seg_mp4)
        # Caption offsets must use the clip's REAL duration: -shortest ends the
        # clip at the audio length, not at d, so accumulating d drifts the subs
        # ~0.12s late per segment (voice ends up ahead of the captions).
        actual = probe_duration(seg_mp4)
        for (w, s, e) in words:
            all_words.append((w, t0 + s, t0 + e))
        durations.append(actual); seg_files.append(seg_mp4)
        t0 += actual
        print(f"  segment {i+1}/{len(segs)} ok ({actual:.1f}s)")

    # branded "Subscribe" end card after the narration
    outro = WORK / "outro.mp4"
    make_outro(outro)
    seg_files.append(outro)

    # concat
    listf = WORK / "list.txt"
    listf.write_text("".join(f"file '{f.as_posix()}'\n" for f in seg_files), encoding="utf-8")
    body = WORK / "body.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listf), "-c", "copy", str(body)])

    # captions (ASS) + optional music -> final.  Run from WORK so subtitles=subs.ass is a simple path.
    if karaoke and all_words:
        build_karaoke_ass(all_words, WORK / "subs.ass", title=brief["title"])
    else:
        build_ass(segs, durations, WORK / "subs.ass", title=brief["title"])
    final = OUT / f"{slug}.mp4"
    music = pick_music()
    if music:
        print(f"music: {music.name}")
        run(["ffmpeg", "-y", "-i", "body.mp4", "-stream_loop", "-1", "-i", str(music.resolve()),
             "-filter_complex",
             "[0:v]subtitles=subs.ass[v];[1:a]volume=0.06[m];"
             "[0:a][m]amix=inputs=2:duration=first:normalize=0[a]",
             "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "21",
             "-c:a", "aac", "-ar", "44100", "-shortest", str(final.resolve())], cwd=str(WORK))
    else:
        run(["ffmpeg", "-y", "-i", "body.mp4", "-vf", "subtitles=subs.ass",
             "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-c:a", "copy",
             str(final.resolve())], cwd=str(WORK))

    # thumbnail: frame + big title text
    # Thumbnail from body.mp4 (no burned captions/hook) -> clean b-roll + title band only.
    thumb = OUT / f"{slug}.jpg"
    ttext = brief.get("thumbnail_text", "").replace(":", r"\:").replace("'", "")
    p = subprocess.run(
        ["ffmpeg", "-y", "-i", str(body.resolve()), "-vf",
         f"select=eq(n\\,45),scale={W}:{H},"
         f"drawbox=y=ih*0.38:color=black@0.5:width=iw:height=ih*0.24:t=fill,"
         f"drawtext=font='DejaVu Sans':text='{ttext}':fontcolor=white:fontsize=104:"
         f"x=(w-text_w)/2:y=(h-text_h)/2:box=0",
         "-frames:v", "1", str(thumb.resolve())],
        capture_output=True, text=True)
    if p.returncode != 0:
        print("thumbnail step skipped:", p.stderr[-300:], file=sys.stderr)

    dur = probe_duration(final)
    print(f"DONE: {final.relative_to(ROOT)}  ({dur:.1f}s, {final.stat().st_size//1024} KB)")


if __name__ == "__main__":
    main()
