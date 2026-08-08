#!/usr/bin/env python3
"""
What can we actually voice with? Read-only probe, no audio generated.

The owner has now rejected three engines as sounding synthetic (edge-tts,
Gemini TTS across six voice/persona combos, and ElevenLabs' old
eleven_multilingual_v2 back in July), so the next step is a better ENGINE
rather than more settings. ElevenLabs is the strongest candidate on quality,
but the account was last touched 2026-06-30 and the plan was flagged
"cancel when convenient", so it may be dead or capped. Building a sample set
against a dead subscription would waste a cycle.

Prints: subscription tier, character quota and usage, whether the newest
models are reachable, and the available voices. Nothing is spent.

Env: ELEVENLABS_API_KEY
"""

import os
import sys

import requests

KEY = os.environ.get("ELEVENLABS_API_KEY")
BASE = "https://api.elevenlabs.io/v1"


def get(path):
    r = requests.get(f"{BASE}/{path}", headers={"xi-api-key": KEY}, timeout=30)
    if r.status_code >= 400:
        return None, f"{r.status_code}: {r.text[:200]}"
    return r.json(), None


def main():
    if not KEY:
        sys.exit("no ELEVENLABS_API_KEY set")

    sub, err = get("user/subscription")
    if err:
        # 401 here is the answer we came for: the key or the plan is gone.
        print(f"subscription: UNREACHABLE {err}")
    else:
        used = sub.get("character_count")
        cap = sub.get("character_limit")
        print(f"tier: {sub.get('tier')}  status: {sub.get('status')}")
        print(f"characters: {used}/{cap} used, resets {sub.get('next_character_count_reset_unix')}")
        if isinstance(used, int) and isinstance(cap, int) and cap:
            print(f"headroom: {cap - used} chars ({round(100 * used / cap)}% used)")

    models, err = get("models")
    if err:
        print(f"models: UNREACHABLE {err}")
    else:
        print("models:")
        for m in models:
            mid = m.get("model_id", "")
            langs = len(m.get("languages") or [])
            print(f"  {mid:32} tts={m.get('can_do_text_to_speech')} "
                  f"langs={langs} name={m.get('name')}")

    voices, err = get("voices")
    if err:
        print(f"voices: UNREACHABLE {err}")
    else:
        vs = voices.get("voices") or []
        print(f"voices: {len(vs)}")
        for v in vs[:30]:
            labels = v.get("labels") or {}
            desc = ", ".join(f"{k}={x}" for k, x in labels.items() if k in
                             ("accent", "age", "gender", "use_case", "description"))
            print(f"  {v.get('voice_id')}  {v.get('name'):22} {desc}")


if __name__ == "__main__":
    main()
