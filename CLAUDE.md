# Snackbyte AI — YouTube automation pipeline

Faceless YouTube Shorts channel, 3 videos/day, ~$0/mo, fully automated via
GitHub Actions. This file is the ops runbook: any Claude session (laptop,
claude.ai/code, mobile) should read it before touching anything.

## Architecture (one video = one publish run)

`publish.yml` (crons 11:13 / 16:13 / 20:13 UTC = 12:13/17:13/21:13 UK BST):
1. **Pick format by slot** — UTC hour <15 battle, <18 news, else comic.
   Push-event runs may override via `format=battle|news|comic` in
   `.github/publish-trigger.txt` (cron runs always use the clock).
2. **Generate brief** (`automation/generate_brief.py`) — LLM provider chain
   Gemini free tier → Claude → GitHub Models. Output validated hard
   (`_clean_battle/_clean_comic/_clean_news`); news ABORTS rather than ship
   hallucinated stories. News stories come from `news_sources.py` (free RSS
   + HN, no keys).
3. **Render** (`render_video.py`) — Gemini TTS (roster of 6 voices, seeded by
   slug; ElevenLabs = automatic fallback) → take-gating (WER, pitch,
   style-leak detection via faster-whisper) → Remotion motion graphics →
   ffmpeg mux (loudnorm -14 LUFS, alimiter level=disabled). Scene-render
   failure falls back to a plain Pexels b-roll render and marks the receipt
   `fmt=<x>-FALLBACK`.
4. **Audio QA gate** (`audio_qa.py --gate`) — blocks upload on silent mix,
   garbled speech (WER>0.35), ≥3s black screen, duration outside 15-178s.
   Peak/monotone stay ADVISORY (AAC overshoots peak; do not gate on it).
5. **Upload** (`upload_video.py`) — YouTube + playlist per format + receipt.
6. **Crosspost** (`crosspost.py`) — IG Reels + FB Reels (via a public GitHub
   Release asset URL) + TikTok (FILE_UPLOAD; posts are PRIVATE until the
   TikTok app passes Production audit).

## Receipts — read these FIRST when something breaks

Committed one-liners in `.github/` (job logs need admin; receipts don't):
- `last-brief.txt` — brief outcome; on failure carries the error log tail
- `last-render.txt`, `last-audio-qa.txt`, `last-upload.txt` (slug, privacy,
  URL, `fmt=`, `pl=`), `last-crosspost.txt` (`ig=/fb=/tt=`), `last-art.txt`,
  `last-token-test.txt`

## Self-healing (self-heal.yml)

- Failed publish run → auto-retried once; second failure → ONE `watchdog`
  issue (titled NEEDS A HUMAN when the receipt greps as credentials/quota).
- Slot backstops 12:48/17:48/21:48 UTC re-dispatch publish.yml when the
  GitHub cron never fired (it silently ate the 12:13 slot on 2026-07-05).
- `watchdog.yml` (13:45 UTC daily) checks upload freshness ≤26h.
- `tests.yml` runs `tests/` (pure-function tests) on every automation push —
  a red X on a commit means DO NOT let the next cron run it; fix first.

## Triggers (push to fire; keep prose free of bare `format=`/`limit=`/`model=`)

- `.github/publish-trigger.txt` — full pipeline (may carry `format=...`)
- `.github/trigger.txt` — brief only ("news"/"comic" in text picks format)
- `.github/render-trigger.txt` — render only; `art-trigger.txt` — avatars
  (may carry `limit=N model=X`); `token-check-trigger.txt` — YT scope probe

## Hard-won rules (violating these caused real incidents)

1. **Never edit code via the GitHub web editor** — a pasted hot-fix with
   smart quotes + stripped newlines bricked all briefs on 2026-07-05.
2. **"Re-run" on a failed run re-executes its ORIGINAL commit**, not current
   main — AND "Pick format" re-reads the clock, so re-running a slot after
   its boundary silently changes the video format (a re-run news slot once
   generated a comic). To test a fix, push a trigger instead.
3. **Music only from the YouTube Audio Library** (committed pool in
   assets/music + manifest.json). Pixabay caused a global Content ID block.
   NCS/Infraction/MokkaMusic "preview/watermark" files are claim-risky —
   never commit them.
4. **Every CI step that pushes to main must `git pull --rebase` + retry** —
   push races killed runs and once destroyed a $1.50 art batch.
5. **Stage receipt files one-by-one** in `git add` (a single missing path
   makes a combined add stage NOTHING — lost a run's receipts 2026-07-05).
6. Deps are PINNED in requirements.txt — bump one at a time, never blind.
7. Avatars: gpt-image-1-mini ONLY (portrait 1024x1536, background=
   transparent). Pollinations/Gemini/gpt-image-2 all failed — do not retry
   them (see git history). VISUALS ARE FROZEN — no avatar/style work.
8. TTS style prompts: keep SHORT; Gemini sometimes speaks them aloud
   (`_style_leaked` gates this). Review any NEW format's first render
   frame-by-frame — telemetry alone missed the style-leak bug.
9. Do not push to main while a publish/art run is mid-flight if avoidable.
10. Secrets go ONLY in GitHub repo secrets — never in chat, code, or files.

## Out-of-domain (needs the human)

Google/YouTube token re-mint (OAuth playground, scopes
`youtube` + `yt-analytics.readonly`), Gemini/OpenAI quota or billing,
TikTok Production audit, Meta token expiry, ElevenLabs subscription
(fallback voice dies if cancelled).

## Strategy state (2026-07-06)

Channel is pre-traction (near-zero views; young channel + API lag). All
engineering is DONE and FROZEN — effort goes to demand (hooks, topics,
retention), not polish. Weekly analytics Sunday 08:00 UTC
(`analytics/latest.md`, hook/format retention tables). **Kill/scale rule:
by 2026-08-18, median Short <~200 views → change format/niche, NOT more
polish.** Affiliate goal: Synthesia live; Pictory next; Jasper/Speechify
gated on traffic. Owner is UK-based.

## Session log (cross-device attribution — KEEP UPDATED)

Multiple Claude sessions touch this repo (laptop, claude.ai/code web,
mobile). ANY session that changes code or makes a notable finding must
append an entry here (date, surface, branch, one-line summary) in the same
commit, so the other sessions know who did what.

- 2026-07-05/06 — laptop Claude Code session (direct commits to main):
  diagnosed + fixed the 2026-07-05 outage (a32ac7d: restored
  _extract_first_json_block, thinkingBudget=0, temp 0.8, slug-collision
  loop, publish.yml brief error capture, upload num_retries, fallback
  receipt marker; 138c5c2: chat_json fresh-completion retry after the job
  log confirmed a missing-comma JSON as root cause). Shipped the
  self-sustaining layer (d264d44: pinned requirements, tests/ + tests.yml,
  self-heal.yml retry+backstops), token-check workflow + playlists
  (9ce669a), watchdog auto-close (4ac064d), runbooks. Verified live news
  publish end-to-end (youtu.be/xEaXeFMiriU, IG+FB+TikTok ok). Deleted
  local claim-risky music files (untracked). gh CLI now authenticated on
  the laptop.
- 2026-07-06 — claude.ai/code web session, branch
  `claude/pipeline-health-check-gtnyzy` (merged to main via PR #1):
  health check + audit + hardening. Diagnosed the 2026-07-05 20:13
  scheduled publish failure as the smart-quote brick in generate_brief.py
  line 142 (fix already on main, a32ac7d; the 23:43/23:55 runs went
  green) — the 16:13 failure was the separate missing-comma JSON case the
  laptop session fixed in 138c5c2. Findings fixed on the branch: receipt
  pushes swallowed lost races via `|| echo "nothing to record"` (now
  rebase-retry x3 + fail loudly), bare `git push` in generate-brief/
  weekly-research (retry added), save-brief + character-art retry loops
  succeeded silently on exhaustion (now exit 1), no timeout-minutes on any
  job (added — a hang could starve the next cron slot via the concurrency
  group), crosspost.py had zero request timeouts (added) and release
  assets accumulated forever (now pruned each run). Watchdog auto-close:
  found independently by both sessions the same night; main's version
  (4ac064d) kept on rebase. pl=fail from 2026-07-05 upload: playlists were
  created by the 00:07 token check; next upload confirms.
