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
# Key pool: two free-tier keys (separate Google accounts) double the daily
# TTS quota; rotation happens automatically on quota errors.
GEM_KEYS = [k for k in (os.environ.get("GEMINI_API_KEY"),
                        os.environ.get("GEMINI_API_KEY_2")) if k]
GEM_KEY = GEM_KEYS[0] if GEM_KEYS else None
# Voice provider: Gemini TTS (free tier) is the default — it beat ElevenLabs
# on the 2026-07-02 A/B (pitch variation AND word accuracy, user-confirmed by
# ear). ElevenLabs remains a manual override / automatic fallback.
VOICE_PROVIDER = os.environ.get("VOICE_PROVIDER") or ("gemini" if GEM_KEY else "eleven")
VOICE_ID = os.environ.get("VOICE_ID") or "Fahco4VZzobUeiPqni1S"      # user-picked library voice
EL_MODEL = os.environ.get("ELEVEN_MODEL") or "eleven_multilingual_v2"
GEMINI_TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")

# Voice roster: a different presenter per video (deterministic by slug), mixed
# genders, each with its own delivery style. GEMINI_VOICE/GEMINI_STYLE repo
# vars override the rotation with a single fixed voice.
VOICE_ROSTER = [
    ("Puck",   "Say this like an excited sports commentator calling a match, fast and punchy: "),
    ("Fenrir", "Say this with deep intense hype, like a boxing ring announcer building to a knockout: "),
    ("Orus",   "Say this fast and confident, like a tech reviewer dropping hot takes: "),
    ("Kore",   "Say this with sharp energetic confidence, like a host about to reveal a winner: "),
    ("Aoede",  "Say this bright, playful and fast-paced, like an excited friend sharing a secret: "),
    ("Leda",   "Say this crisp and punchy, like a sports desk anchor calling the highlights: "),
]
GEMINI_VOICE = os.environ.get("GEMINI_VOICE")            # optional fixed override
GEMINI_STYLE = os.environ.get("GEMINI_STYLE")            # optional fixed override
_gem_voice = VOICE_ROSTER[0][0]
_gem_style = VOICE_ROSTER[0][1]


def select_gemini_voice(slug):
    """Pick this video's presenter: seeded by slug so retries of the same
    video keep the same voice while different videos rotate."""
    global _gem_voice, _gem_style
    if GEMINI_VOICE:
        _gem_voice = GEMINI_VOICE
        _gem_style = GEMINI_STYLE or VOICE_ROSTER[0][1]
    else:
        _gem_voice, _gem_style = random.Random(slug).choice(VOICE_ROSTER)
        if GEMINI_STYLE:
            _gem_style = GEMINI_STYLE
    if VOICE_PROVIDER == "gemini":
        print(f"gemini voice: {_gem_voice}")
# Expressive delivery: low stability = more variation between sentences, high
# style = more emotion. The old 0.4/0.25 sounded like reading from a book.
VOICE_SETTINGS = {
    "stability": float(os.environ.get("VOICE_STABILITY", "0.35")),
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


_gem_key_idx = 0


def tts_gemini(text, dest, voice=None, style=None):
    """Gemini TTS (free tier): returns 24kHz PCM, converted to mp3 via ffmpeg.
    Rotates across the key pool on quota errors. voice/style override the
    video-level presenter (used for per-character hero voices)."""
    global _gem_key_idx
    last = ""
    for attempt in range(2 * max(1, len(GEM_KEYS))):
        key = GEM_KEYS[_gem_key_idx % len(GEM_KEYS)]
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_TTS_MODEL}:generateContent",
                params={"key": key},
                json={
                    "contents": [{"parts": [{"text": (style or _gem_style) + text}]}],
                    "generationConfig": {
                        "responseModalities": ["AUDIO"],
                        "speechConfig": {"voiceConfig": {
                            "prebuiltVoiceConfig": {"voiceName": voice or _gem_voice}}},
                    },
                },
                timeout=180,
            )
        except requests.RequestException as e:
            last = str(e); import time; time.sleep(3 * (attempt + 1)); continue
        if r.status_code < 400:
            part = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
            raw = dest.with_suffix(".pcm")
            raw.write_bytes(base64.b64decode(part["data"]))
            run(["ffmpeg", "-y", "-f", "s16le", "-ar", "24000", "-ac", "1",
                 "-i", str(raw), "-b:a", "128k", str(dest)])
            raw.unlink(missing_ok=True)
            return
        last = f"{r.status_code}: {r.text[:200]}"
        if r.status_code == 429 and len(GEM_KEYS) > 1:
            _gem_key_idx += 1                      # quota hit: next key in pool
            print(f"    gemini key quota hit; rotating key", file=sys.stderr)
            continue
        if r.status_code in (429, 500, 502, 503):
            import time; time.sleep(5 * (attempt + 1)); continue
        break
    raise RuntimeError(f"gemini tts failed ({last})")


def _whisper_words(path):
    """Word timings via forced transcription: Gemini TTS has no timestamp API,
    so the karaoke captions align to what Whisper hears."""
    global _WHISPER
    from faster_whisper import WhisperModel
    if _WHISPER is None:
        _WHISPER = WhisperModel("tiny.en", device="cpu", compute_type="int8")
    segs, _ = _WHISPER.transcribe(str(path), language="en", beam_size=1,
                                  word_timestamps=True)
    words = []
    for s in segs:
        for w in (s.words or []):
            token = w.word.strip()
            if token:
                words.append((token, w.start, w.end))
    return words


def tts(text, dest, voice=None, style=None):
    if VOICE_PROVIDER == "gemini":
        try:
            return tts_gemini(text, dest, voice, style)
        except Exception as e:
            if not EL_KEY:
                raise
            print(f"  gemini voice failed ({e}); falling back to ElevenLabs", file=sys.stderr)
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


def tts_timed(text, dest, voice=None, style=None):
    """TTS with word timings. Returns [(word, start_s, end_s)] or raises if unavailable."""
    if VOICE_PROVIDER == "gemini":
        try:
            tts_gemini(text, dest, voice, style)
            words = _whisper_words(dest)
            if not words:
                raise RuntimeError("no word timings recoverable from gemini audio")
            return words
        except Exception as e:
            # Gemini free tier can hit daily quota; fall back to ElevenLabs
            # while its key still exists so the cron never misses a day.
            if not EL_KEY:
                raise
            print(f"  gemini voice failed ({e}); falling back to ElevenLabs", file=sys.stderr)
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


def _pitch_std(path):
    """Voice pitch variation in semitones, or None if unmeasurable.
    Uses librosa (available in CI); silently skips where its DLLs are broken."""
    try:
        import numpy as np
        import librosa
        p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le",
                            "-ac", "1", "-ar", "22050", "-"], capture_output=True)
        if p.returncode != 0:
            return None
        y = np.frombuffer(p.stdout, dtype=np.float32)
        f0 = librosa.yin(y, fmin=60, fmax=350, sr=22050)
        f0 = f0[(f0 > 65) & (f0 < 340)]
        if len(f0) < 30:
            return None
        return float(np.std(12 * np.log2(f0 / np.median(f0))))
    except Exception:
        return None


FLAT_TAKE = 1.2      # semitone std below this = flat delivery, worth one retry
MAX_WER = 0.35       # word error rate above this = garbled take, worth one retry

_WHISPER = None


def _transcribe(path):
    """Speech-to-text via faster-whisper (tiny.en). None if unavailable."""
    global _WHISPER
    try:
        from faster_whisper import WhisperModel
        if _WHISPER is None:
            _WHISPER = WhisperModel("tiny.en", device="cpu", compute_type="int8")
        segs, _ = _WHISPER.transcribe(str(path), language="en", beam_size=1)
        return " ".join(s.text for s in segs)
    except Exception as e:
        print(f"    transcription unavailable ({e})", file=sys.stderr)
        return None


def _wer(expected, path):
    """Word error rate of the spoken take vs the script. None if unmeasurable.
    Catches garbled TTS: pitch checks can't hear mangled words, Whisper can."""
    hyp = _transcribe(path)
    if hyp is None:
        return None

    def norm(s):
        return re.sub(r"[^a-z0-9' ]+", " ", s.lower()).split()

    r, h = norm(expected), norm(hyp)
    if not r:
        return None
    d = list(range(len(h) + 1))
    for i, rw in enumerate(r, 1):
        prev, d[0] = d[0], i
        for j, hw in enumerate(h, 1):
            cur = d[j]
            d[j] = min(d[j] + 1, d[j - 1] + 1, prev + (rw != hw))
            prev = cur
    return d[len(h)] / len(r)


def _take_score(ps, wer):
    """Rank takes: intelligibility dominates, liveliness breaks ties."""
    w = (1.0 - min(wer, 1.0)) if wer is not None else 0.6
    p = min((ps or 0) / 3.0, 1.0)
    return w * 10 + p


def tts_take(text, dest, voice=None, style=None):
    """TTS with word timings, re-taking weak deliveries once. A take is weak
    when it is garbled (high WER vs the script) or flat (low pitch variation).
    TTS is non-deterministic, so a second take usually fixes it; the
    better take wins. Returns (words, pitch_std_or_None)."""
    takes = []                                   # (path, words, ps, wer)
    for attempt in range(2):
        f = dest if attempt == 0 else dest.with_suffix(".take2.mp3")
        try:
            words = tts_timed(text, f, voice, style)
        except Exception:
            if attempt == 0:
                raise
            break
        ps, wer = _pitch_std(f), _wer(text, f)
        takes.append((f, words, ps, wer))
        garbled = wer is not None and wer > MAX_WER
        flat = ps is not None and ps < FLAT_TAKE
        if not garbled and not flat:
            break
        if attempt == 0:
            why = f"wer={wer:.2f}" if garbled else f"pitch={ps:.2f}st"
            print(f"    weak take ({why}); re-taking")
    best = max(takes, key=lambda t: _take_score(t[2], t[3]))
    if best[0] != dest:
        shutil.move(str(best[0]), str(dest))
        print(f"    retake wins (wer={best[3]}, pitch={best[2]})")
    for f, *_ in takes:
        if f != dest:
            Path(f).unlink(missing_ok=True)
    return best[1], best[2]


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
    """Battle format: one presenter voice, BattleShort composition."""
    battle = brief["battle"]
    props = dict(battle)
    _render_scenes(brief, "BattleShort", props,
                   f"Battle render: {battle['toolA']} vs {battle['toolB']}")


def render_comic(brief):
    """AI Toolverse episode: narrator + per-hero character voices, ComicShort."""
    comic = brief["comic"]
    uni_file = ROOT / "automation" / "universe.json"
    vmap = {}
    if uni_file.exists():
        uni = json.loads(uni_file.read_text(encoding="utf-8"))
        vmap = {h["tool"]: (h.get("voice"), h.get("speak")) for h in uni.get("heroes", [])}
    narrator = (None, "Narrate this like an epic anime trailer, dark and dramatic: ")
    voices = [narrator]
    for h in comic["heroes"]:
        v, persona = vmap.get(h["tool"], (None, None))
        style = (f"You are {h['alias']}, {persona}. Say this fully in character, "
                 "with theatrical superhero energy: ") if persona else None
        voices.append((v, style))
    voices.append(narrator)
    props = {"episodeTitle": brief["title"], "threat": comic["threat"],
             "heroes": comic["heroes"], "resolution": comic["resolution"]}
    _render_scenes(brief, "ComicShort", props,
                   f"Toolverse episode: {comic['threat']}", voices=voices)


def _render_scenes(brief, comp, props, label, voices=None):
    """Shared scene renderer: TTS per scene -> Remotion motion graphics sized
    to the narration audio -> mux delayed narration + captions + music.
    voices = optional per-scene [(voice, style)] for multi-character episodes.
    Any failure raises; the caller falls back to the classic b-roll render."""
    slug = brief["slug"]
    segs = brief["narration"]        # scene count validated at brief time
    n = len(segs)
    print(f"{label}  ({n} scenes)")

    # 1. narration audio per scene (+ word timings for karaoke captions)
    audios, words_per, durs, karaoke = [], [], [], True
    for i, seg in enumerate(segs):
        audio = WORK / f"a{i}.mp3"
        v, style = (voices[i] if voices and i < len(voices) else (None, None))
        try:
            words, ps = tts_take(seg["text"], audio, voice=v, style=style)
            words_per.append(words)
        except Exception as e:
            print(f"  word timings unavailable ({e}); plain TTS", file=sys.stderr)
            karaoke = False
            tts(seg["text"], audio, voice=v, style=style)
            words_per.append([])
            ps = None
        audios.append(audio)
        durs.append(probe_duration(audio))
        note = f", pitch {ps:.2f}st" if ps is not None else ""
        print(f"  scene {i+1}/{n} voiced ({durs[-1]:.1f}s{note})")

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
    props = dict(props)
    props["sceneFrames"] = {"intro": frames[0], "rounds": frames[1:-1], "verdict": frames[-1]}
    props_file = WORK / "props.json"
    props_file.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    graphics = WORK / "battle.mp4"
    run([NPX, "remotion", "render", "src/index.ts", comp, str(graphics.resolve()),
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
    # loudnorm to YouTube's -14 LUFS: roster voices vary in level and the
    # voice+music sum was measured clipping (peak 1.11) without it
    filters.append("".join(alabels) + f"amix=inputs={len(alabels)}:duration=longest:normalize=0[mix]")
    filters.append("[mix]loudnorm=I=-14:TP=-1.5:LRA=11[a]")
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
    if VOICE_PROVIDER == "gemini" and not GEM_KEY:
        sys.exit("VOICE_PROVIDER=gemini needs GEMINI_API_KEY")
    if VOICE_PROVIDER != "gemini" and not EL_KEY:
        sys.exit("ELEVENLABS_API_KEY must be set (or set GEMINI_API_KEY for the free voice)")
    if not PX_KEY:
        sys.exit("PEXELS_API_KEY must be set")
    print(f"voice provider: {VOICE_PROVIDER}")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        sys.exit("ffmpeg/ffprobe not found on PATH")

    brief = pick_brief()
    slug = brief["slug"]
    segs = brief["narration"]
    select_gemini_voice(slug)
    print(f"Rendering: {brief['title']}  ({len(segs)} segments)")

    scene_render = None
    if (REMOTION_DIR / "package.json").exists():
        if brief.get("comic"):
            scene_render = render_comic
        elif brief.get("battle"):
            scene_render = render_battle
    if scene_render:
        try:
            _reset_work()
            scene_render(brief)
            return
        except KeyboardInterrupt:
            raise
        except BaseException as e:      # incl. SystemExit from run(): keep the cron alive
            print(f"scene render failed ({e}); falling back to b-roll render", file=sys.stderr)

    _reset_work()

    durations, seg_files, all_words, karaoke = [], [], [], True
    t0 = 0.0
    for i, seg in enumerate(segs):
        audio = WORK / f"a{i}.mp3"
        words = []
        try:
            words, _ = tts_take(seg["text"], audio)      # natural voice + word timings + flat-take retry
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
             "[0:a][m]amix=inputs=2:duration=first:normalize=0[mix];"
             "[mix]loudnorm=I=-14:TP=-1.5:LRA=11[a]",
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
