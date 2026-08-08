#!/usr/bin/env python3
"""
Narration-only voice samples, so the presenter gets picked by ear instead of
guessed at.

Why this exists: GEMINI_VOICE was pinned to Puck on 2026-07-10 for the AI-tool
BATTLE format, and Puck's roster style is "excited sports commentator, fast and
punchy". The channel has since pivoted to mind/body insight explainers, but the
voice persona never moved with it, so every psychology explainer ships in a
sports-commentary read. Guessing at replacements has misfired repeatedly; the
thing that has actually worked on this project is rendering real options and
letting the owner choose.

Each candidate speaks the WHOLE narration in ONE Gemini TTS call, which is the
same single-pass shape render_video uses in production (_voice_single_pass), so
a sample sounds like what would actually ship. Audio only: no Remotion render,
no upload, so a full comparison costs a handful of TTS calls.

Env:
  GEMINI_API_KEY (+ GEMINI_API_KEY_2)  required, same pool as the pipeline
  BRIEF_SLUG                           optional, defaults to the newest brief
  VOICE_CANDIDATES                     optional, comma-separated labels to run
Output: output/samples/<n>_<voice>_<label>.mp3
"""

import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import render_video as rv

OUT = rv.ROOT / "output" / "samples"

# Style prompts are kept SHORT on purpose: Gemini TTS prepends the style to the
# text and occasionally reads it aloud (rule 8, _style_leaked exists for that).
#
# "control" is exactly what production ships today, so the comparison has a
# baseline instead of only alternatives. The rest trade the match-calling
# energy for the register an explainer actually wants: unhurried, curious,
# talking to one person.
CANDIDATES = [
    ("control-sports", "Puck",
     "Say this like an excited sports commentator calling a match, fast and punchy: "),
    ("curious-friend", "Puck",
     "Say this calmly and curiously, like telling a friend a fascinating fact: "),
    ("calm-explainer", "Charon",
     "Say this calmly and clearly, unhurried, like explaining something interesting: "),
    ("warm-conversational", "Sulafat",
     "Say this warmly and conversationally, unhurried: "),
    ("intrigued", "Aoede",
     "Say this like sharing a surprising discovery, warm and clear: "),
    ("documentary", "Vindemiatrix",
     "Say this like a documentary narrator, calm and measured: "),
]


def script_from(brief):
    """The full narration as one block, matching how _voice_single_pass feeds
    the whole script to TTS in a single continuous read."""
    segs = brief.get("narration") or []
    texts = [s["text"].strip() for s in segs if s.get("text")]
    if not texts:
        sys.exit("brief has no narration")
    return " ".join(texts)


def main():
    if not rv.GEM_KEYS:
        sys.exit("no GEMINI_API_KEY set: samples must use the production voice "
                 "path, edge-tts would prove nothing")

    brief = rv.pick_brief()
    script = script_from(brief)
    wanted = [s.strip() for s in (os.environ.get("VOICE_CANDIDATES") or "").split(",") if s.strip()]
    runs = [c for c in CANDIDATES if not wanted or c[0] in wanted]

    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.mp3"):
        f.unlink()

    print(f"brief: {brief.get('slug')} ({len(script.split())} words)")
    made = []
    for i, (label, voice, style) in enumerate(runs, 1):
        dest = OUT / f"{i}_{voice}_{label}.mp3"
        try:
            rv.tts_gemini(script, dest, voice=voice, style=style)
        except SystemExit as e:
            # One bad voice name or a quota blip must not lose the whole set.
            print(f"  {label} ({voice}): FAILED {e}", file=sys.stderr)
            continue
        print(f"  {label} ({voice}) -> {dest.name}")
        made.append({"label": label, "voice": voice, "style": style, "file": dest.name})

    if not made:
        sys.exit("no samples rendered")
    (OUT / "samples.json").write_text(
        json.dumps({"slug": brief.get("slug"), "title": brief.get("title"),
                    "script": script, "samples": made}, indent=2), encoding="utf-8")
    print(f"{len(made)}/{len(runs)} samples in {OUT}")


if __name__ == "__main__":
    main()
