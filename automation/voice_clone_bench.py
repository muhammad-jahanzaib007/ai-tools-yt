#!/usr/bin/env python3
"""Benchmark Chatterbox TTS on a CI runner, before committing to a voice swap.

Why this exists (2026-09-18): the owner asked whether the channel could narrate
in his own voice. Kokoro, the current free engine, has no zero-shot cloning at
all (fixed voicepacks only), so using his voice means changing engine, not
changing a setting. Chatterbox (Resemble AI, MIT licence, commercial use fine)
clones from a few seconds of reference audio with no training.

The open question is not licence or quality, it is SPEED: renders run on
CPU-only GitHub runners. Vendor figures quote Chatterbox-Nano at ~3x realtime
on 8 cores; the free runner has fewer, so this measures the real number on the
real machine before any pipeline change is made.

Two modes:
  * no REFERENCE_AUDIO  -> built-in voice. Proves install, model download and
    CPU throughput.
  * REFERENCE_AUDIO set -> clones that clip. This is the mode that answers
    "does it sound like me".

Prints a one-line verdict and writes the wav for a human to listen to. It does
NOT touch the pipeline: nothing here is imported by render_video.py.
"""

import os
import sys
import time
from pathlib import Path

TEXT = os.environ.get(
    "BENCH_TEXT",
    "Your brain fills in your blind spot without telling you. Every time you "
    "look at something, there is a gap in your vision where the optic nerve "
    "leaves the eye, and your brain quietly paints over it with whatever is "
    "nearby. You never notice, because the edit happens before you see it."
)
REFERENCE = os.environ.get("REFERENCE_AUDIO", "").strip()
OUT = Path(os.environ.get("BENCH_OUT", "voice-bench"))


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    import torch
    from chatterbox.tts import ChatterboxTTS

    cores = os.cpu_count()
    print(f"runner: {cores} CPU cores, torch {torch.__version__}, device=cpu")

    t0 = time.time()
    model = ChatterboxTTS.from_pretrained(device="cpu")
    load_s = time.time() - t0
    print(f"model load (incl. download): {load_s:.1f}s")

    kwargs = {}
    if REFERENCE:
        ref = Path(REFERENCE)
        if not ref.exists():
            sys.exit(f"REFERENCE_AUDIO set but not found: {ref}")
        kwargs["audio_prompt_path"] = str(ref)
        print(f"cloning reference: {ref.name} ({ref.stat().st_size / 1024:.0f} KB)")
    else:
        print("no REFERENCE_AUDIO: using the built-in voice (speed check only)")

    t0 = time.time()
    wav = model.generate(TEXT, **kwargs)
    gen_s = time.time() - t0

    dest = OUT / ("clone.wav" if REFERENCE else "builtin.wav")
    import torchaudio
    torchaudio.save(str(dest), wav, model.sr)

    # From the tensor, not python's `wave`: torchaudio writes float32 WAVs
    # (format tag 3) and `wave` raises "unknown format: 3" on those. That is
    # what failed run 35285729364 AFTER synthesis had already succeeded.
    audio_s = wav.shape[-1] / float(model.sr)
    ratio = audio_s / gen_s if gen_s else 0
    print(f"generated {audio_s:.1f}s of audio in {gen_s:.1f}s -> {ratio:.2f}x realtime")

    # A 30s narration is the pipeline's typical length. The existing insight
    # render budget is ~10 min end to end, so anything that keeps synthesis
    # under ~2 min is comfortably affordable; under 1 min is a non-issue.
    projected = 30 / ratio if ratio else float("inf")
    print(f"projected synthesis for a 30s narration: {projected:.0f}s")
    verdict = ("VIABLE" if projected <= 120 else
               "MARGINAL" if projected <= 300 else "TOO SLOW")
    print(f"VERDICT: {verdict} on this runner "
          f"(load {load_s:.0f}s is once per run, not per sentence)")


if __name__ == "__main__":
    main()
