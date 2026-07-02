#!/usr/bin/env python3
"""Audio QA after a render: is the voiceover expressive, is the mix sane?

Measures, from the narration clips in .render/ and the newest output mp4:
- voice pitch variation in semitones (std of f0 around its median):
  under ~1.5 = monotone "reading from a book", 2-4 = lively speech
- final-mix RMS/peak and duration
Writes a one-line summary to stdout and .github/last-audio-qa.txt so results
are reviewable with git alone (repo is private, no public API).

Runs in CI (ubuntu: ffmpeg + librosa work there). Never fails the build.
"""
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


def main():
    parts = []
    voice = sorted((ROOT / ".render").glob("a*.mp3"))
    if voice:
        try:
            y = np.concatenate([load_audio(v) for v in voice])
            ps = pitch_std_semitones(y)
            if ps is not None:
                verdict = "MONOTONE" if ps < 1.5 else ("ok" if ps < 2.2 else "expressive")
                parts.append(f"voice_pitch_std={ps:.2f}st({verdict})")
        except Exception as e:
            parts.append(f"voice_qa_error={str(e)[:80]}")
    outs = sorted((ROOT / "output").glob("*.mp4"), key=lambda p: p.stat().st_mtime)
    if outs:
        try:
            y = load_audio(outs[-1])
            parts.append(f"mix_rms={np.sqrt(np.mean(y**2)):.3f} "
                         f"peak={np.max(np.abs(y)):.2f} dur={len(y)/SR:.0f}s")
        except Exception as e:
            parts.append(f"mix_qa_error={str(e)[:80]}")
    line = " ".join(parts) or "no audio found"
    print("AUDIO-QA:", line)
    (ROOT / ".github" / "last-audio-qa.txt").write_text(line + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
