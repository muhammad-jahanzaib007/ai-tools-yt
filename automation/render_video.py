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
import time
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
EDGE_VOICE = os.environ.get("EDGE_VOICE") or "en-US-AndrewNeural"    # free edge-tts fallback voice
EL_MODEL = os.environ.get("ELEVEN_MODEL") or "eleven_multilingual_v2"
GEMINI_TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")

# Voice roster: a different presenter per video (deterministic by slug), mixed
# genders, each with its own delivery style. GEMINI_VOICE/GEMINI_STYLE repo
# vars override the rotation with a single fixed voice.
# Puck's style = the EXACT prompt that produced the owner-approved DaVinci
# render (2026-07-09). Measured: that read was ~2.8wps on 36-word segments —
# fast but FLOWING. The "rushed/shouty" complaint came from feeding this
# prompt 16-word fragments (7 disconnected reads); the fix is LONG segments
# (see RANKING_BULLETS/BATTLE_BULLETS), not a slower prompt — an "unhurried,
# pause after each sentence" variant read slow AND still choppy.
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
# 1.0 = Gemini's native pace. Was 1.15 (a 15% atempo speed-up), which the
# owner heard as fast/"pitched" (2026-07-14). Gemini's own pace is already
# brisk with the single-pass continuous read, so no artificial speed-up.
VOICE_SPEED = float(os.environ.get("VOICE_SPEED", "1.0"))
VOICE_SETTINGS = {
    "stability": float(os.environ.get("VOICE_STABILITY", "0.35")),
    "similarity_boost": float(os.environ.get("VOICE_SIMILARITY", "0.75")),
    "style": float(os.environ.get("VOICE_STYLE", "0.55")),
    "use_speaker_boost": True,
    "speed": VOICE_SPEED,
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
            # Gemini TTS has no speed control; adjust here with atempo
            # (pitch-preserving) only when asked. At native speed (~1.0) skip
            # the filter entirely so there is no resample artifact. Done before
            # Whisper alignment so the karaoke captions still match the audio.
            af = (["-filter:a", f"atempo={VOICE_SPEED}"]
                  if abs(VOICE_SPEED - 1.0) > 0.02 else [])
            run(["ffmpeg", "-y", "-f", "s16le", "-ar", "24000", "-ac", "1",
                 "-i", str(raw)] + af + ["-b:a", "128k", str(dest)])
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


def _whisper_words(path, prompt=None):
    """Word timings via forced transcription: Gemini TTS has no timestamp API.
    `prompt` (the script) is passed as Whisper's initial_prompt to bias it
    toward the real vocabulary — but the caption TEXT is corrected against the
    script in _align_script_to_timings, so a mishear here is not fatal."""
    global _WHISPER
    from faster_whisper import WhisperModel
    if _WHISPER is None:
        _WHISPER = WhisperModel("tiny.en", device="cpu", compute_type="int8")
    segs, _ = _WHISPER.transcribe(str(path), language="en", beam_size=1,
                                  word_timestamps=True,
                                  initial_prompt=prompt or None)
    words = []
    for s in segs:
        for w in (s.words or []):
            token = w.word.strip()
            if token:
                words.append((token, w.start, w.end))
    return words


def _align_script_to_timings(text, whisper_words):
    """Whisper mishears brand names — it captions 'ChatGPT' as 'Chachi Pt'.
    We have the exact script, so keep Whisper's word TIMINGS but use the
    SCRIPT's spelling: align the two token streams and substitute the script
    words onto the audio timeline. Whisper-only hallucinations are dropped;
    script words Whisper missed get a slice of the local gap. Falls back to the
    raw Whisper words if either side is empty."""
    import difflib
    script = text.split()
    if not script or not whisper_words:
        return whisper_words

    def norm(w):
        return re.sub(r"[^a-z0-9]+", "", w.lower())

    s_norm = [norm(w) for w in script]
    w_norm = [norm(w) for (w, _, _) in whisper_words]
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
            a=s_norm, b=w_norm, autojunk=False).get_opcodes():
        if tag == "equal":
            for si, wi in zip(range(i1, i2), range(j1, j2)):
                _, st, en = whisper_words[wi]
                out.append((script[si], st, en))
        elif tag == "replace":
            span = whisper_words[j1:j2]
            t0, t1, n = span[0][1], span[-1][2], i2 - i1
            if t1 <= t0:
                t1 = t0 + 0.3 * n
            step = (t1 - t0) / n
            for k, si in enumerate(range(i1, i2)):
                out.append((script[si], t0 + k * step, t0 + (k + 1) * step))
        elif tag == "delete":
            prev_end = out[-1][2] if out else whisper_words[0][1]
            nxt = whisper_words[j2][1] if j2 < len(whisper_words) else prev_end + 0.3 * (i2 - i1)
            n = i2 - i1
            if nxt <= prev_end:
                nxt = prev_end + 0.3 * n
            step = (nxt - prev_end) / n
            for k, si in enumerate(range(i1, i2)):
                out.append((script[si], prev_end + k * step, prev_end + (k + 1) * step))
        # tag == "insert": Whisper heard words not in the script -> drop them
    return out or whisper_words


def tts_edge(text, dest, voice=None):
    """Free fallback voice via Microsoft edge-tts: no API key, no quota. Produces
    an mp3; word timings are recovered by Whisper (like the Gemini path), so a
    Gemini free-tier quota-out (2026-07-22 blocked every slot) can no longer
    stop a render. Raises if no audio is produced."""
    import asyncio
    import edge_tts
    v = voice or EDGE_VOICE

    async def _run():
        comm = edge_tts.Communicate(text, v)
        with open(dest, "wb") as f:
            async for ch in comm.stream():
                if ch["type"] == "audio":
                    f.write(ch["data"])

    asyncio.run(_run())
    if not Path(dest).exists() or Path(dest).stat().st_size < 800:
        raise RuntimeError("edge-tts produced no audio")


def _el_tts(text, dest, timestamps):
    """ElevenLabs REST call. `timestamps` uses the alignment endpoint (returns
    word timings); otherwise plain audio. Raises on HTTP error."""
    suffix = "/with-timestamps" if timestamps else ""
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}{suffix}",
        params={"output_format": "mp3_44100_128"},
        headers={"xi-api-key": EL_KEY, "Content-Type": "application/json"},
        json={"text": text, "model_id": EL_MODEL, "voice_settings": VOICE_SETTINGS},
        timeout=120,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"ElevenLabs {r.status_code}: {r.text[:200]}")
    return r


def tts(text, dest, voice=None, style=None):
    # Gemini (owner's chosen voice) -> edge-tts (free) -> ElevenLabs.
    if VOICE_PROVIDER == "gemini":
        try:
            return tts_gemini(text, dest, voice, style)
        except Exception as e:
            print(f"  gemini voice failed ({e}); falling back to edge-tts", file=sys.stderr)
    try:
        return tts_edge(text, dest)
    except Exception as e:
        if not EL_KEY:
            raise
        print(f"  edge-tts failed ({e}); falling back to ElevenLabs", file=sys.stderr)
    dest.write_bytes(_el_tts(text, dest, timestamps=False).content)


def _whisper_timed(text, dest):
    """Word timings for `dest` via Whisper, captioned with the SCRIPT's spelling
    (so 'ChatGPT' is never captioned as Whisper's 'Chachi Pt'). Raises if none."""
    words = _whisper_words(dest, prompt=text)
    if not words:
        raise RuntimeError("no word timings recoverable from audio")
    return _align_script_to_timings(text, words)


def tts_timed(text, dest, voice=None, style=None):
    """TTS with word timings. Returns [(word, start_s, end_s)] or raises if unavailable.
    Provider chain: Gemini -> edge-tts (free, no quota) -> ElevenLabs."""
    if VOICE_PROVIDER == "gemini":
        try:
            tts_gemini(text, dest, voice, style)
            return _whisper_timed(text, dest)
        except Exception as e:
            print(f"  gemini voice failed ({e}); falling back to edge-tts", file=sys.stderr)
    # edge-tts: free, no key, no quota. Timings via Whisper (edge audio is clean,
    # so it transcribes accurately) - keeps a quota-out day publishing.
    try:
        tts_edge(text, dest)
        return _whisper_timed(text, dest)
    except Exception as e:
        if not EL_KEY:
            raise
        print(f"  edge-tts failed ({e}); falling back to ElevenLabs", file=sys.stderr)
    r = _el_tts(text, dest, timestamps=True)
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
# Words-per-second above this = the "rushed sprint" the owner flagged
# (2026-07-11: a published video measured 3.36wps AFTER the DaVinci-conditions
# prompt fix — the prompt alone doesn't hold the pace; the take gate must).
# The owner-approved DaVinci render read at ~2.8wps. Only measured on
# segments of PACE_MIN_WORDS+ (short hooks are legitimately quick).
PACE_MAX = 3.05
PACE_MIN_WORDS = 12


def _pace(text, words):
    """Words-per-second of a take: script word count over spoken time from
    the take's word timings. None when too short to judge or unmeasurable."""
    n = len(_norm_words(text))
    if n < PACE_MIN_WORDS or not words:
        return None
    end = words[-1][2]
    if not end or end <= 0:
        return None
    return n / end

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


def _norm_words(s):
    return re.sub(r"[^a-z0-9' ]+", " ", s.lower()).split()


def _wer(expected, path):
    """(word error rate, transcript) of the spoken take vs the script.
    (None, None) if unmeasurable. Catches garbled TTS: pitch checks can't
    hear mangled words, Whisper can."""
    hyp = _transcribe(path)
    if hyp is None:
        return None, None

    r, h = _norm_words(expected), _norm_words(hyp)
    if not r:
        return None, hyp
    d = list(range(len(h) + 1))
    for i, rw in enumerate(r, 1):
        prev, d[0] = d[0], i
        for j, hw in enumerate(h, 1):
            cur = d[j]
            d[j] = min(d[j] + 1, d[j - 1] + 1, prev + (rw != hw))
            prev = cur
    return d[len(h)] / len(r), hyp


def _style_leaked(style, text, hyp):
    """True when the TTS spoke its style instruction aloud (Gemini prepends the
    style prompt to the text and occasionally reads it: the first news render
    opened with '...fast but perfectly clear.' on screen). Detected as several
    distinctive style-prompt words appearing early in the transcript."""
    if not style or hyp is None:
        return False
    text_words = set(_norm_words(text))
    distinct = [w for w in _norm_words(style) if w not in text_words and len(w) > 3]
    if not distinct:
        return False
    head = _norm_words(hyp)[:len(_norm_words(style)) + 8]
    hits = sum(1 for w in distinct if w in head)
    return hits >= 2


def _take_score(ps, wer, leaked=False, pace=None):
    """Rank takes: intelligibility dominates, liveliness breaks ties.
    A take that spoke its style prompt aloud is heavily penalised; a rushed
    take loses up to 3 points so an in-pace take of similar clarity wins."""
    w = (1.0 - min(wer, 1.0)) if wer is not None else 0.6
    p = min((ps or 0) / 3.0, 1.0)
    rush = min((pace - PACE_MAX) * 4.0, 3.0) if pace is not None and pace > PACE_MAX else 0.0
    return w * 10 + p - (8 if leaked else 0) - rush


def tts_take(text, dest, voice=None, style=None):
    """TTS with word timings, re-taking weak deliveries once. A take is weak
    when it is garbled (high WER vs the script), flat (low pitch variation),
    or spoke the style prompt aloud. TTS is non-deterministic, so a second
    take usually fixes it; the better take wins.
    Returns (words, pitch_std_or_None)."""
    eff_style = style or (_gem_style if VOICE_PROVIDER == "gemini" else None)
    takes = []                                   # (path, words, ps, wer, leaked, pace)
    for attempt in range(2):
        f = dest if attempt == 0 else dest.with_suffix(".take2.mp3")
        try:
            words = tts_timed(text, f, voice, style)
        except Exception:
            if attempt == 0:
                raise
            break
        ps, (wer, hyp) = _pitch_std(f), _wer(text, f)
        leaked = _style_leaked(eff_style, text, hyp)
        pace = _pace(text, words)
        takes.append((f, words, ps, wer, leaked, pace))
        garbled = wer is not None and wer > MAX_WER
        flat = ps is not None and ps < FLAT_TAKE
        rushed = pace is not None and pace > PACE_MAX
        if not garbled and not flat and not leaked and not rushed:
            break
        if attempt == 0:
            why = ("style prompt spoken aloud" if leaked
                   else f"wer={wer:.2f}" if garbled
                   else f"pitch={ps:.2f}st" if flat
                   else f"pace={pace:.2f}wps")
            print(f"    weak take ({why}); re-taking")
    best = max(takes, key=lambda t: _take_score(t[2], t[3], t[4], t[5]))
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


def _stage_ranking_media(brief):
    """Stage per-tool favicons into remotion/public/ranking/ (gitignored).
    Screenshots were removed 2026-07-14 (owner: "just don't add app previews" —
    desktop homepage captures never fit a portrait Short cleanly). The ranking
    format is now pure typographic motion; favicons stay as a small brand cue,
    best-effort, with a letter-monogram fallback in the composition when a real
    favicon isn't available."""
    pub = REMOTION_DIR / "public" / "ranking"
    if pub.exists():
        shutil.rmtree(pub)
    pub.mkdir(parents=True)
    by_name = {l["name"].lower(): l.get("url", "")
               for l in brief.get("links", [])
               if isinstance(l, dict) and l.get("name")}
    logos = {}
    for it in brief["ranking"]["items"]:
        url = by_name.get(it["name"].lower(), "")
        if not url:
            continue
        rank = it["rank"]
        dom = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
        if dom:
            ldest = pub / f"logo{rank}.png"
            try:
                r = requests.get("https://www.google.com/s2/favicons",
                                 params={"domain": dom, "sz": "128"}, timeout=30)
                # A tiny payload is Google's generic globe placeholder - skip it.
                if r.status_code < 400 and len(r.content) > 500:
                    ldest.write_bytes(r.content)
                    logos[str(rank)] = ldest.name
            except requests.RequestException:
                pass
    print(f"  ranking logos: {len(logos)}/5 staged")
    return logos


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


def _margin_at(t, margins):
    """MarginV override for a caption starting at time t (0 = use style default).
    margins = [(start_s, end_s, marginV)] windows for scenes whose layout
    occupies the default caption zone (e.g. ranking's bottom info block)."""
    for (s, e, m) in margins or []:
        if s <= t < e:
            return m
    return 0


def build_karaoke_ass(words, path, group=4, title=None, margins=None):
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
        mv = _margin_at(start, margins)
        lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Cap,,0,0,{mv},,{text}")
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


def build_ass_at(segs, delays, durs, path, margins=None):
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
            mv = _margin_at(st, margins)
            lines.append(f"Dialogue: 0,{_ts(st)},{_ts(en)},Cap,,0,0,{mv},,{safe}")
            st = en
    path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")


def render_battle(brief):
    """Battle format: one presenter voice, BattleShort composition."""
    battle = brief["battle"]
    props = dict(battle)
    _render_scenes(brief, "BattleShort", props,
                   f"Battle render: {battle['toolA']} vs {battle['toolB']}")


def render_ranking(brief):
    """Top-5 countdown: one presenter voice, RankingShort composition.
    Pure typographic motion on a cohesive dark single-accent stage (no app
    screenshots — owner 2026-07-14); favicon/monogram as a small brand cue."""
    ranking = brief["ranking"]
    logos = _stage_ranking_media(brief)
    props = {"theme": ranking["theme"], "items": ranking["items"],
             "cta": ranking["cta"], "logos": logos}
    # rank scenes carry a 760px bottom info block (name/tag/reason) — lift the
    # burned-in captions above it (block top is 760 from bottom; 830 clears
    # the border with a gap; intro/outro keep the default 360).
    _render_scenes(brief, "RankingShort", props,
                   f"Ranking render: {ranking['theme']}", lift_captions=830)


# Short on purpose: long style prompts raise the odds Gemini TTS reads the
# instruction aloud (happened on the first news render; _style_leaked gates it).
NEWS_ANCHOR_STYLE = "Say the following like an urgent, confident news anchor:\n\n"


def render_news(brief):
    """Daily AI news: one anchor voice, NewsShort composition."""
    news = brief["news"]
    props = {"dateLabel": news["dateLabel"], "headline": news["headline"],
             "stories": news["stories"], "outro": news["outro"]}
    voices = [(None, NEWS_ANCHOR_STYLE)] * len(brief["narration"])
    _render_scenes(brief, "NewsShort", props,
                   f"AI news render: {news['dateLabel']}", voices=voices)


def _art_slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _key_white(src, dest):
    """Copy a character PNG with its background made transparent so it
    composites cleanly onto the comic scenes.

    Uses an edge flood-fill rather than a brightness threshold: gpt-image-1
    renders a warm off-white/beige backdrop (~217,206,191), well under any
    "near-white" cutoff, so a threshold key removed nothing. Flood-filling from
    the edges strips the connected background at any colour while leaving the
    character (and same-coloured interior pixels not touching an edge) intact.
    """
    from PIL import Image, ImageDraw
    im = Image.open(src).convert("RGBA")
    w, h = im.size
    # If the art already has a real transparent background (gpt-image-1 renders
    # one directly), keep it as-is — flooding would only risk damage.
    corners = [im.getpixel(p)[3] for p in ((0, 0), (w-1, 0), (0, h-1), (w-1, h-1))]
    if sum(c < 16 for c in corners) >= 3:
        im.save(dest)
        return
    rgb = im.convert("RGB")
    SENT = (255, 0, 255)                     # sentinel unlikely to occur in art
    seeds = [(0, 0), (w-1, 0), (0, h-1), (w-1, h-1),
             (w//2, 0), (w//2, h-1), (0, h//2), (w-1, h//2)]
    for s in seeds:
        ImageDraw.floodfill(rgb, s, SENT, thresh=42)
    src_px, out_px = rgb.load(), im.load()
    for y in range(h):
        for x in range(w):
            if src_px[x, y] == SENT:
                r, g, b, a = out_px[x, y]
                out_px[x, y] = (r, g, b, 0)
    im.save(dest)


def _stage_art(slugs_files):
    """Key out white + copy the needed art into remotion/public/toolverse/.
    Returns the set of successfully staged filenames."""
    art_dir = ROOT / "assets" / "toolverse"
    pub = REMOTION_DIR / "public" / "toolverse"
    pub.mkdir(parents=True, exist_ok=True)
    staged = set()
    for fname in slugs_files:
        src = art_dir / fname
        if src.exists():
            try:
                _key_white(src, pub / fname)
                staged.add(fname)
            except Exception as e:
                print(f"  art stage failed {fname}: {e}", file=sys.stderr)
    return staged


def render_comic(brief):
    """AI Toolverse episode: narrator + per-hero character voices, animated
    character avatars fighting, ComicShort."""
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

    # stage the avatar art (white keyed to transparent) and attach slugs
    threat_slug = _art_slug(comic["threat"])
    heroes = []
    want = [f"villain-{threat_slug}-menace.png", f"villain-{threat_slug}-defeated.png"]
    for h in comic["heroes"]:
        hs = _art_slug(h["tool"])
        heroes.append({**h, "slug": hs})
        want += [f"hero-{hs}-idle.png", f"hero-{hs}-action.png"]
    staged = _stage_art(want)
    print(f"  staged {len(staged)}/{len(want)} avatar files")
    missing = set(want) - staged
    if missing:
        # Better a plain b-roll video than a comic with invisible characters:
        # raising here lands in main()'s fallback to the Pexels render.
        raise RuntimeError(f"avatar art missing: {', '.join(sorted(missing))}")

    props = {"episodeTitle": brief["title"], "threat": comic["threat"],
             "threatSlug": threat_slug, "heroes": heroes,
             "resolution": comic["resolution"]}
    _render_scenes(brief, "ComicShort", props,
                   f"Toolverse episode: {comic['threat']}", voices=voices)


def _thumb_props(brief, props):
    """Props for the 16:9 Thumb composition, per format. Rankings pass the
    staged favicon strip (rank 1..5); battles pass the two tool names."""
    if brief.get("ranking"):
        r = brief["ranking"]
        items = sorted(r["items"], key=lambda x: x["rank"])
        logos = props.get("logos") or {}
        strip = [logos[str(it["rank"])] for it in items if str(it["rank"]) in logos]
        return {"kind": "ranking", "title": r["theme"],
                "badge": f"TOP {len(items)}", "logos": strip, "logoDir": "ranking"}
    if brief.get("battle"):
        b = brief["battle"]
        return {"kind": "battle", "title": b.get("tagline", ""),
                "toolA": b["toolA"], "toolB": b["toolB"]}
    if brief.get("news"):
        return {"kind": "news", "title": brief["news"]["headline"], "badge": "AI NEWS"}
    if brief.get("comic"):
        return {"kind": "comic", "title": brief.get("title", ""), "badge": "AI TOOLVERSE"}
    return {"kind": "ranking", "title": brief.get("title", ""), "badge": ""}


CUT_TAIL_S = 0.12    # audio kept after a scene's last word
CUT_LEAD_S = 0.10    # audio kept before a scene's first word


def _scene_cut_points(scene_words, full_dur):
    """Per-scene (start, end) slice times in the single-pass narration.
    Cuts hug the scene's own words instead of splitting the inter-scene gap
    down the middle: the midpoint cut kept the front half of every pause in
    the outgoing clip — breath intake plus the pre-voicing of the NEXT
    scene's first word (Whisper start timestamps miss the onset), heard as
    the voice starting a word and stopping (owner 2026-07-16). Keep a short
    natural tail/lead and drop the middle of the gap entirely; the caps at
    30% of the gap keep tiny gaps from producing overlapping clips."""
    n = len(scene_words)
    pts = []
    for i, sw in enumerate(scene_words):
        if i == 0:
            start = 0.0
        else:
            prev = scene_words[i - 1]
            pe = prev[-1][2] if prev else (sw[0][1] if sw else 0.0)
            cs = sw[0][1] if sw else pe
            gap = max(0.0, cs - pe)
            start = cs - min(CUT_LEAD_S, 0.3 * gap)
        if i == n - 1:
            end = full_dur
        else:
            nxt = scene_words[i + 1]
            ce = sw[-1][2] if sw else start
            ns = nxt[0][1] if nxt else ce
            gap = max(0.0, ns - ce)
            end = ce + min(CUT_TAIL_S, 0.3 * gap)
        end = max(end, start + 0.20)
        pts.append((start, end))
    return pts


def _silences(path, noise_db=-30.0, min_dur=0.04):
    """Silence intervals [(start, end), ...] in `path` via ffmpeg silencedetect.
    Lets the scene slicer cut inside a real pause rather than at a Whisper word
    timestamp (which marks a word's start late, so a timestamp cut let the next
    scene's first word bleed into this clip's tail). A cut inside detected
    silence never splits a word and needs no timestamp accuracy."""
    try:
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-i", str(path), "-af",
             f"silencedetect=noise={noise_db}dB:d={min_dur}", "-f", "null", "-"],
            stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
    except Exception:
        return []
    sil, cur = [], None
    for line in (r.stderr or "").splitlines():
        m = re.search(r"silence_start:\s*([-\d.]+)", line)
        if m:
            cur = float(m.group(1)); continue
        m = re.search(r"silence_end:\s*([-\d.]+)", line)
        if m and cur is not None:
            sil.append((cur, float(m.group(1)))); cur = None
    return sil


def _voice_single_pass(segs, voice, style):
    """Voice the WHOLE script in ONE TTS call, then slice it per scene at word
    boundaries. Gemini TTS restarts its pitch/energy on every call, so one call
    per scene (5-7 tiny reads) made the voice audibly change pitch between
    sections (owner report 2026-07-13). A single continuous read holds one
    pitch across the whole video — and it's also 1 free-tier request instead of
    5-7. Returns (audios, words_per, durs) shaped exactly like the per-scene
    loop. Raises if word timings are unavailable so the caller can fall back."""
    combined = " ".join(s["text"].strip() for s in segs)
    full = WORK / "narration_full.mp3"
    words, _ps = tts_take(combined, full, voice=voice, style=style)
    if not words:
        raise RuntimeError("no word timings for single-pass narration")
    # tts_take retakes a garbled take once, but across the WHOLE 100+ word
    # script both takes can still contain a bad patch (one mangled span tanks
    # the whole-pass WER). Recording the whole thing again is just as likely to
    # garble somewhere, so instead RAISE here: the caller falls back to the
    # per-scene loop, where each short segment is voiced + retaken on its own
    # and a single bad scene can't poison the rest. Without this the garbled
    # pass sailed through to the Audio QA gate and failed the entire run
    # (2026-07-17: wer 0.76 blocked a slot; a full rerun is 8min vs a ~30s
    # per-scene re-voice).
    wer, _hyp = _wer(combined, full)
    if wer is not None and wer > MAX_WER:
        raise RuntimeError(f"single-pass narration garbled (wer={wer:.2f}); per-scene")
    full_dur = probe_duration(full)
    # words map 1:1 onto combined.split() (that is what _align_script_to_timings
    # emits), so scene boundaries fall on cumulative per-scene word counts.
    counts = [len(s["text"].split()) for s in segs]
    scene_words, idx = [], 0
    for c in counts:
        scene_words.append(words[idx:idx + c]); idx += c
    if idx < len(words):                     # alignment drift -> last scene keeps the rest
        scene_words[-1] += words[idx:]
    # SILENCE-BASED scene boundaries (owner's idea, 2026-07-19): the continuous
    # read already pauses between scenes (each scene ends a sentence). Detect
    # those pauses and cut each boundary INSIDE the silence, so a clip ends after
    # its last word and the next clip starts before its first word - no word is
    # split and the next scene's onset never bleeds into this clip's tail.
    # This removes the dependency on Whisper word timestamps (marked late, which
    # caused the bleed) entirely. Where a boundary has no detectable pause
    # (scenes ran together), fall back to the asymmetric timestamp cut: a short
    # tail after the last word, never past ~45% of the gap toward the next word.
    sils = _silences(full)
    n = len(segs)
    bounds = []                                  # cut time between scene i and i+1
    for i in range(n - 1):
        cur, nxt = scene_words[i], scene_words[i + 1]
        ce = cur[-1][2] if cur else 0.0          # this scene's last word end
        ns = nxt[0][1] if nxt else ce            # next scene's first word start
        near = [(s, e) for (s, e) in sils if e > ce - 0.20 and s < ns + 0.20]
        if near:
            mid = (ce + ns) / 2.0
            s, e = min(near, key=lambda iv: abs((iv[0] + iv[1]) / 2 - mid))
            cut = (s + e) / 2.0                  # inside the real pause
        else:
            gap = max(0.0, ns - ce)
            cut = ce + max(0.06, min(0.12, 0.45 * gap))
        bounds.append(cut)
    audios, words_per, durs = [], [], []
    for i, sw in enumerate(scene_words):
        start = 0.0 if i == 0 else bounds[i - 1]
        end = full_dur if i == n - 1 else bounds[i]
        end = max(end, start + 0.20)
        clip = WORK / f"a{i}.mp3"
        run(["ffmpeg", "-y", "-i", str(full.resolve()), "-ss", f"{start:.3f}",
             "-to", f"{end:.3f}", "-b:a", "128k", str(clip.resolve())])
        audios.append(clip)
        durs.append(probe_duration(clip))
        words_per.append([(w, max(0.0, s - start), max(0.05, e - start))
                          for (w, s, e) in sw])
    return audios, words_per, durs


def _render_scenes(brief, comp, props, label, voices=None, lift_captions=0):
    """Shared scene renderer: TTS per scene -> Remotion motion graphics sized
    to the narration audio -> mux delayed narration + captions + music.
    voices = optional per-scene [(voice, style)] for multi-character episodes.
    lift_captions = nonzero MarginV applied to MID scenes only (not intro/
    outro) when the format's scene layout occupies the default caption zone —
    ranking's 760px bottom info block was overlapping the reason text.
    Any failure raises; the caller falls back to the classic b-roll render."""
    slug = brief["slug"]
    segs = brief["narration"]        # scene count validated at brief time
    n = len(segs)
    print(f"{label}  ({n} scenes)")

    # 1. narration audio per scene (+ word timings for karaoke captions).
    # Single-voice formats (battle/ranking/news) record the whole script in one
    # continuous take then slice it, so the voice never changes pitch between
    # scenes; multi-character comics keep per-scene voices.
    audios, words_per, durs, karaoke = [], [], [], True
    single = voices is None or len(set(voices)) == 1
    if single:
        sv, ss = ((None, None) if voices is None else voices[0])
        try:
            audios, words_per, durs = _voice_single_pass(segs, sv, ss)
            for i, d in enumerate(durs):
                print(f"  scene {i+1}/{n} voiced ({d:.1f}s) [single-pass]")
        except Exception as e:
            print(f"  single-pass voice failed ({e}); per-scene", file=sys.stderr)
            audios, words_per, durs = [], [], []

    if not audios:
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

    # 4. captions timed to the delayed narration. Clamp each word inside its
    # own scene's audio window so a Whisper timing wobble can never drift a
    # caption past the voice it belongs to (keeps subs and voiceover locked).
    all_words = []
    for i, ws in enumerate(words_per):
        d = durs[i]
        for (w, s, e) in ws:
            s2 = max(0.0, min(s, d))
            e2 = max(s2 + 0.05, min(e, d))
            all_words.append((w, delays[i] + s2, delays[i] + e2))
    margins = None
    if lift_captions and n > 2:
        margins = [(starts[i], starts[i] + frames[i] / FPS, lift_captions)
                   for i in range(1, n - 1)]
    if karaoke and all_words:
        build_karaoke_ass(all_words, WORK / "subs.ass",     # no hook overlay: VsIntro is the hook
                          margins=margins)
    else:
        build_ass_at(segs, delays, durs, WORK / "subs.ass", margins=margins)

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
    # alimiter defaults level=true, which re-normalizes back toward 0 dBFS and
    # undoes loudnorm's -1.5 dBTP headroom -> AAC+resample overshoot then clips.
    # level=disabled keeps loudnorm's level; limit=0.89 leaves room for ISP.
    filters.append("[mix]loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=level=disabled:limit=0.89[a]")
    filters.append("[0:v]subtitles=subs.ass[v]")
    final = OUT / f"{slug}.mp4"
    run(["ffmpeg", "-y"] + inputs + [
        "-filter_complex", ";".join(filters),
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "21",
        "-c:a", "aac", "-ar", "44100",
        "-t", f"{total_sec:.3f}", str(final.resolve())], cwd=str(WORK))

    # 6. thumbnail: a dedicated 16:9 hook card (Thumb composition) so the watch
    # page / search / shares get an edge-to-edge thumbnail with big readable
    # text — the old 9:16 frame-grab was letterboxed into 16:9 with ugly blur
    # bars. (Shorts feed ignores custom thumbnails regardless.) Falls back to
    # the frame-grab if the still render fails, so a run never ships thumbless.
    thumb = OUT / f"{slug}.jpg"
    made = False
    try:
        tp = WORK / "thumbprops.json"
        tp.write_text(json.dumps(_thumb_props(brief, props), ensure_ascii=False),
                      encoding="utf-8")
        run([NPX, "remotion", "still", "src/index.ts", "Thumb",
             str(thumb.resolve()), f"--props={tp.resolve()}", "--frame=0",
             "--log=error"], cwd=str(REMOTION_DIR))
        made = thumb.exists()
    except Exception as e:
        print(f"thumb card render failed ({e}); frame-grab fallback", file=sys.stderr)
    if not made:
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
    # No voice-key requirement: edge-tts (free, no key) is the guaranteed floor
    # of the Gemini -> edge-tts -> ElevenLabs chain, so a render is never blocked
    # on a missing/quota-out paid voice key.
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
        if brief.get("news"):
            scene_render = render_news
        elif brief.get("comic"):
            scene_render = render_comic
        elif brief.get("ranking"):
            scene_render = render_ranking
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
            # Marker so the upload receipt shows fmt=<x>-FALLBACK: without it a
            # persistent scene-render bug ships plain b-roll daily and telemetry
            # still reads like the real format shipped.
            OUT.mkdir(exist_ok=True)
            (OUT / f"{slug}.fallback").write_text(
                f"{type(e).__name__}: {e}\n", encoding="utf-8")

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
             "[mix]loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=level=disabled:limit=0.89[a]",
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
