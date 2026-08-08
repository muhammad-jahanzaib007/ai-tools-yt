#!/usr/bin/env python3
"""
Narration-only voice samples, so the presenter gets picked by ear instead of
guessed at.

Round 1 (2026-08-08) sampled six Gemini voice+persona combos and the owner
rejected all six as sounding synthetic, which was the third engine rejected
after edge-tts and ElevenLabs' old eleven_multilingual_v2. So this compares
ENGINES, not settings: better models rather than a different persona on the
same model.

Each candidate speaks the WHOLE narration in ONE call, which is the same
single-pass shape render_video uses in production (_voice_single_pass), so a
sample sounds like what would actually ship. Audio only: no Remotion render, no
upload.

Note on ElevenLabs: the repo key authenticates for text-to-speech but is
scope-restricted (no user_read/models_read/voices_read, confirmed by
voice_probe.py), so the reachable models and voices cannot be enumerated in
advance. Candidates are therefore attempted and the ones the API refuses are
reported as failures rather than silently dropped. Do not treat an unlisted
model as unavailable until a call has actually failed.

Env:
  GEMINI_API_KEY (+ _2)   for gemini candidates
  ELEVENLABS_API_KEY      for eleven candidates
  BRIEF_SLUG              optional, defaults to the newest brief
  VOICE_CANDIDATES        optional, comma-separated labels to run
Output: output/samples/<n>_<engine>_<label>.mp3
"""

import os
import sys
import json
import subprocess
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

import render_video as rv

OUT = rv.ROOT / "output" / "samples"
EL_KEY = os.environ.get("ELEVENLABS_API_KEY")

# ElevenLabs premade voice ids are stable across accounts. Picked for a calm
# conversational register rather than the "announcer" energy the channel has
# been shipping. If a id is wrong the API 400s and the candidate is reported
# failed, so nothing here is assumed correct.
EL_VOICES = {
    "brian":     "nPczCjzI2devNBz1zQrb",
    "jessica":   "cgSgspJ2msm6clMCkdW9",
    "daniel":    "onwK4e9ZLuTAKqWW03F9",
    "charlotte": "XB0fDUnXU5powFXDhCwa",
}

# Style prompts stay SHORT: Gemini prepends them to the text and sometimes reads
# them aloud (rule 8, _style_leaked). Only kept here for the control sample.
SPORTS = "Say this like an excited sports commentator calling a match, fast and punchy: "

# engine, label, params. The Gemini control is what production ships today, so
# the comparison has a baseline the owner has already heard in context.
CANDIDATES = [
    ("gemini", "control-current", {"voice": "Puck", "style": SPORTS}),
    ("eleven", "v3-brian",     {"voice": "brian",     "model": "eleven_v3"}),
    ("eleven", "v3-jessica",   {"voice": "jessica",   "model": "eleven_v3"}),
    ("eleven", "v2-brian",     {"voice": "brian",     "model": "eleven_multilingual_v2"}),
    ("eleven", "v2-charlotte", {"voice": "charlotte", "model": "eleven_multilingual_v2"}),
    ("eleven", "turbo-daniel", {"voice": "daniel",    "model": "eleven_turbo_v2_5"}),
    ("kokoro", "kokoro-am",    {"voice": "am_michael"}),
    ("kokoro", "kokoro-bf",    {"voice": "bf_emma"}),
]


def script_from(brief):
    """The full narration as one block, matching how _voice_single_pass feeds
    the whole script to TTS in a single continuous read."""
    segs = brief.get("narration") or []
    texts = [s["text"].strip() for s in segs if s.get("text")]
    if not texts:
        sys.exit("brief has no narration")
    return " ".join(texts)


def tts_eleven(text, dest, voice, model):
    """Direct ElevenLabs call. Deliberately does NOT reuse render_video.tts_el:
    that one is pinned to the module-level VOICE_ID/EL_MODEL globals, and the
    whole point here is varying both. Voice settings are omitted so each model
    applies its own defaults (v3 rejects some of the v2 setting shapes)."""
    vid = EL_VOICES.get(voice, voice)
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{vid}",
        params={"output_format": "mp3_44100_128"},
        headers={"xi-api-key": EL_KEY, "Content-Type": "application/json"},
        json={"text": text, "model_id": model},
        timeout=180,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"ElevenLabs {r.status_code}: {r.text[:220]}")
    dest.write_bytes(r.content)


def tts_kokoro(text, dest, voice):
    """Kokoro via kokoro-onnx: the free local model flagged back on 2026-07-22
    as the better free floor than edge-tts, never actually tried until now.
    Model files are fetched by the workflow; absent them this raises and the
    candidate is reported failed rather than silently skipped."""
    import numpy as np
    import soundfile as sf
    from kokoro_onnx import Kokoro

    model = rv.ROOT / "kokoro-v1.0.onnx"
    voices = rv.ROOT / "voices-v1.0.bin"
    if not model.exists() or not voices.exists():
        raise RuntimeError("kokoro model files not downloaded")
    k = Kokoro(str(model), str(voices))
    samples, rate = k.create(text, voice=voice, speed=1.0, lang="en-us")
    wav = dest.with_suffix(".wav")
    sf.write(str(wav), np.asarray(samples), rate)
    subprocess.run(["ffmpeg", "-y", "-i", str(wav), "-b:a", "128k", str(dest)],
                   capture_output=True, check=True)
    wav.unlink(missing_ok=True)


def main():
    brief = rv.pick_brief()
    script = script_from(brief)
    wanted = [s.strip() for s in (os.environ.get("VOICE_CANDIDATES") or "").split(",") if s.strip()]
    runs = [c for c in CANDIDATES if not wanted or c[1] in wanted]

    OUT.mkdir(parents=True, exist_ok=True)
    for f in list(OUT.glob("*.mp3")) + list(OUT.glob("*.json")):
        f.unlink()

    print(f"brief: {brief.get('slug')} ({len(script.split())} words)")
    made, failed = [], []
    for i, (engine, label, p) in enumerate(runs, 1):
        dest = OUT / f"{i}_{engine}_{label}.mp3"
        try:
            if engine == "gemini":
                if not rv.GEM_KEYS:
                    raise RuntimeError("no GEMINI_API_KEY")
                rv.tts_gemini(script, dest, voice=p["voice"], style=p["style"])
            elif engine == "eleven":
                if not EL_KEY:
                    raise RuntimeError("no ELEVENLABS_API_KEY")
                tts_eleven(script, dest, p["voice"], p["model"])
            elif engine == "kokoro":
                tts_kokoro(script, dest, p["voice"])
            else:
                raise RuntimeError(f"unknown engine {engine}")
        except (SystemExit, Exception) as e:
            # One dead model or voice id must not cost the whole comparison.
            print(f"  {label} ({engine}): FAILED {e}", file=sys.stderr)
            failed.append({"label": label, "engine": engine, "error": str(e)[:220]})
            continue
        print(f"  {label} ({engine}) -> {dest.name}")
        made.append({"label": label, "engine": engine, "params": p, "file": dest.name})

    (OUT / "samples.json").write_text(
        json.dumps({"slug": brief.get("slug"), "title": brief.get("title"),
                    "script": script, "samples": made, "failed": failed}, indent=2),
        encoding="utf-8")
    print(f"{len(made)}/{len(runs)} samples in {OUT}")
    if not made:
        sys.exit("no samples rendered")


if __name__ == "__main__":
    main()
