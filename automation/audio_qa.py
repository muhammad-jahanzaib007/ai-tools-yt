#!/usr/bin/env python3
"""Media QA after a render: is the voiceover expressive, is the mix sane,
does the video actually show something?

Measures, from the narration clips in .render/ and the newest output mp4:
- voice pitch variation in semitones (std of f0 around its median):
  under ~1.5 = monotone "reading from a book", 2-4 = lively speech
- final-mix RMS/peak and duration
- black-screen spans (ffmpeg blackdetect) and Shorts-eligible duration
Writes a one-line summary to stdout and .github/last-audio-qa.txt so results
are reviewable with git alone (repo is private, no public API).

Runs in CI (ubuntu: ffmpeg + librosa work there). Never fails the build
unless invoked with --gate.
"""
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SR = 22050


def load_audio(path):
    """Decode anything ffmpeg reads to mono float32."""
    p = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1",
         "-ar", str(SR), "-"], capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode()[-200:])
    return np.frombuffer(p.stdout, dtype=np.float32)


def pitch_std_semitones(y):
    import librosa
    f0 = librosa.yin(y, fmin=60, fmax=350, sr=SR)
    f0 = f0[(f0 > 65) & (f0 < 340)]              # plausible voiced frames only
    if len(f0) < 50:
        return None
    return float(np.std(12 * np.log2(f0 / np.median(f0))))


def script_wer():
    """Word error rate of all kept takes vs the brief narration. None = skip."""
    try:
        import json
        import re
        from faster_whisper import WhisperModel
        slug = (ROOT / "automation" / "latest.txt").read_text(encoding="utf-8").strip()
        brief = json.loads((ROOT / "briefs" / f"{slug}.json").read_text(encoding="utf-8"))
        expected = " ".join(s["text"] for s in brief["narration"])
        model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
        heard = []
        for v in sorted((ROOT / ".render").glob("a*.mp3")):
            segs, _ = model.transcribe(str(v), language="en", beam_size=1)
            heard.append(" ".join(s.text for s in segs))
        norm = lambda s: re.sub(r"[^a-z0-9' ]+", " ", s.lower()).split()
        r, h = norm(expected), norm(" ".join(heard))
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
    except Exception:
        return None


def speech_pace(voice_files):
    """Words per second across the narration takes: script word count over
    total spoken audio time. Advisory: ~2.3-2.7 wps reads energetic-natural;
    3.0+ is the 'rushed sprint' the owner flagged on 2026-07-11."""
    try:
        import json
        slug = (ROOT / "automation" / "latest.txt").read_text(encoding="utf-8").strip()
        brief = json.loads((ROOT / "briefs" / f"{slug}.json").read_text(encoding="utf-8"))
        words = sum(len(s["text"].split()) for s in brief["narration"])
        total = 0.0
        for v in voice_files:
            y = load_audio(v)
            total += len(y) / SR
        if not words or total < 3:
            return None
        return words / total
    except Exception:
        return None


def black_spans(path):
    """(start, duration) of near-black video spans >=1s via ffmpeg blackdetect."""
    p = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(path),
         "-vf", "blackdetect=d=1:pix_th=0.10", "-an", "-f", "null", "-"],
        capture_output=True, text=True)
    return [(float(m.group(1)), float(m.group(2))) for m in re.finditer(
        r"black_start:([\d.]+)\s+black_end:[\d.]+\s+black_duration:([\d.]+)",
        p.stderr)]


def main():
    # --gate: exit non-zero on UNAMBIGUOUS failures so the publish job aborts
    # BEFORE uploading. Kept deliberately narrow to avoid false positives:
    #  - no/near-silent audio in the final video
    #  - GARBLED speech (high WER)
    #  - a black-screen span >=3s (scenes are colourful gradients; real black
    #    that long means a broken render, not a stylistic fade)
    #  - duration outside 15-178s (>3min loses Shorts eligibility and the
    #    video dies as a regular upload; <15s means the render broke)
    # Fuzzy signals (monotone pitch, mp4 peak) stay advisory only: the mp4 peak
    # is measured from lossy AAC, which overshoots slightly past 1.0 even when
    # the pre-encode mix was limited to 0.89, so it is NOT a reliable clip gate.
    gate = "--gate" in sys.argv
    parts, failures = [], []
    have_voice = False
    voice = sorted((ROOT / ".render").glob("a*.mp3"))
    if voice:
        have_voice = True
        try:
            y = np.concatenate([load_audio(v) for v in voice])
            ps = pitch_std_semitones(y)
            if ps is not None:
                verdict = "MONOTONE" if ps < 1.5 else ("ok" if ps < 2.2 else "expressive")
                parts.append(f"voice_pitch_std={ps:.2f}st({verdict})")
        except Exception as e:
            parts.append(f"voice_qa_error={str(e)[:80]}")
        wer = script_wer()
        if wer is not None:
            verdict = "GARBLED" if wer > 0.35 else ("ok" if wer > 0.15 else "clear")
            parts.append(f"script_wer={wer:.2f}({verdict})")
            if wer > 0.35:
                failures.append(f"garbled speech (wer={wer:.2f})")
        wps = speech_pace(voice)
        if wps is not None:
            verdict = "RUSHED" if wps > 3.0 else ("brisk" if wps > 2.7 else "natural")
            parts.append(f"pace={wps:.2f}wps({verdict})")
    outs = sorted((ROOT / "output").glob("*.mp4"), key=lambda p: p.stat().st_mtime)
    if outs:
        try:
            y = load_audio(outs[-1])
            rms = float(np.sqrt(np.mean(y**2)))
            dur = len(y) / SR
            parts.append(f"mix_rms={rms:.3f} peak={np.max(np.abs(y)):.2f} "
                         f"dur={dur:.0f}s")
            if rms < 0.01:
                failures.append(f"silent mix (rms={rms:.3f})")
            if not 15 <= dur <= 178:
                failures.append(f"duration {dur:.0f}s outside Shorts range 15-178s")
        except Exception as e:
            parts.append(f"mix_qa_error={str(e)[:80]}")
        try:
            spans = black_spans(outs[-1])
            worst = max(spans, key=lambda s: s[1]) if spans else None
            parts.append("black=" + (f"{worst[1]:.1f}s@{worst[0]:.0f}s" if worst else "none"))
            if worst and worst[1] >= 3:
                failures.append(f"black screen {worst[1]:.1f}s at {worst[0]:.0f}s")
        except Exception as e:
            parts.append(f"video_qa_error={str(e)[:80]}")
    else:
        failures.append("no output video")
    if not have_voice and not outs:
        failures.append("no audio found")
    line = " ".join(parts) or "no audio found"
    print("AUDIO-QA:", line)
    (ROOT / ".github" / "last-audio-qa.txt").write_text(line + "\n", encoding="utf-8")
    if gate and failures:
        print("AUDIO-QA GATE FAILED:", "; ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
