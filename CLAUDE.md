# Snackbyte AI — YouTube automation pipeline

Faceless YouTube Shorts channel, 3 videos/day, ~$0/mo, fully automated via
GitHub Actions. This file is the ops runbook: any Claude session (laptop,
claude.ai/code, mobile) should read it before touching anything.

## Operating agreement (owner ↔ Claude — set 2026-07-08)

The owner asked Claude to act as the decision-maker for this channel. The
honest, agreed version of that:

- **Claude drives.** Make strategy + engineering/operational calls
  proactively and decisively — decide and do, don't present menus of
  options. Have an opinion; lead.
- **Claude disagrees openly.** When the owner proposes something Claude
  thinks is a mistake, argue it plainly and don't cave to please. Do not
  rubber-stamp. A decisive operator who tells the truth is the point.
- **The owner keeps final say.** This is the owner's Google account,
  affiliate revenue, and name/"genuine business" signal — they carry every
  consequence, so after hearing Claude's case they can still overrule, and
  Claude respects that. Claude will NOT pre-commit to overriding the owner
  against their will; that would be disrespecting their control over their
  own asset.
- **Human-domain actions stay the owner's** (Claude cannot execute them):
  minting tokens, secrets, billing/quota, creating Google/YouTube accounts,
  deleting videos, TikTok/Meta account actions. Claude escalates these plus
  anything irreversible or account-level; it decides the rest itself.
- **Keep replies TERSE** (owner ask, 2026-07-08). Answer, state the action,
  done. No walls of text, no restating what the owner knows, no option
  menus. Brevity conserves the owner's tokens.

## Architecture (one video = one publish run)

`publish.yml` (crons 11:13 / 16:13 / 20:13 UTC = 12:13/17:13/21:13 UK BST):
1. **Pick format by slot** — normally UTC hour <15 battle, <18 news, else
   comic (schedule runs derive the hour from the cron slot, not now(), so a
   late replay keeps its format). **CURRENTLY BATTLE-ONLY** (2026-07-08
   consolidation): `FORMAT_ONLY="battle"` at the top of the step forces every
   run to battle; set it to `""` to restore the 3-format rotation. While it's
   set, the heartbeat's per-slot format inputs are overridden.
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
- Slot backstops (12:48/17:48/21:48 schedule) were RETIRED 2026-07-08: the
  external heartbeat now covers missed slots per-slot (no over-fire), and an
  in-repo cron backstop dies in a GitHub scheduler outage anyway. The crude
  "no run in 100 min" backstop had over-fired an extra video (2026-07-08).
- `watchdog.yml` (13:45 UTC daily) checks upload freshness ≤26h.
- `tests.yml` runs `tests/` (pure-function tests) on every automation push —
  a red X on a commit means DO NOT let the next cron run it; fix first.
- **`heartbeat/` (Cloudflare Worker) — the EXTERNAL backstop. LIVE since
  2026-07-08.** All the above are GitHub crons, so a wholesale GitHub
  scheduler outage (2026-07-06..08, days long) kills the backstops too. The
  Worker runs on Cloudflare (cron `*/20 * * * *`), checks every slot 35–165
  min out, and workflow_dispatches any that GitHub missed (YT slots pinned to
  their format). Secret `GH_TOKEN` = fine-grained PAT, Actions R/W both repos;
  deploy/rotate is human-domain (see `heartbeat/README.md`). Hit the Worker
  URL in a browser for an on-demand self-test (one line per slot). This is
  what replaced the manual per-slot dispatching during the outage — a session
  should no longer need to hand-fire slots unless the Worker itself is down.

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

## Strategy state (2026-07-08)

Channel is pre-traction (~25 views/28d; young channel + API lag). All
engineering is DONE and FROZEN — effort goes to demand (hooks, topics,
retention), not polish. Weekly analytics Sunday 08:00 UTC
(`analytics/latest.md`, hook/format retention tables). **Kill/scale rule:
by 2026-08-18, median Short <~200 views → change format/niche, NOT more
polish.** Affiliate goal: Synthesia live; Pictory next; Jasper/Speechify
gated on traffic. Owner is UK-based.

**BATTLE-ONLY as of 2026-07-08** (`FORMAT_ONLY="battle"` in publish.yml):
3 formats fragmented the algorithm's audience-building on a pre-traction
channel, so all 3 daily slots now produce tool battles — the format with
the clearest search demand + affiliate fit. News + comic are PAUSED, not
deleted (the code paths are intact; flip `FORMAT_ONLY=""` to restore).
Battle topic supply is ample (13-tool roster, auto-replenished). Plan: prove
battle earns distribution, THEN clone the winner (first to a high-income
language — DE/FR/ES — reusing the engine; NOT different niches, which throw
the engine away). Do not split to more channels/languages before one format
proves out. Cadence held at 3/day (consistency = the point); revisit only if
matchup quality thins.

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
- 2026-07-06 12:36-13:15 — claude.ai/code web session (same as above):
  GitHub's scheduler outage continued into the afternoon — the 11:13
  battle slot AND its 12:48 self-heal backstop were both silently eaten
  (nothing scheduled has fired in either repo all day; the blog's 08:00 +
  08:50 were eaten the same way). Backstops cannot catch a wholesale
  scheduler outage because they are crons too — an external heartbeat
  (e.g. Cloudflare Worker cron hitting workflow_dispatch) is the only
  full fix; proposed to the owner. Slot recovered by manual dispatch at
  12:53: battle Short live + public (youtu.be/2qVfb_OhS3U), audio QA
  clear, IG/FB/TikTok all ok, and pl=ok — confirming the 2026-07-05
  playlist failure is fixed. Web session is covering today's remaining
  slots (16:13, 20:13) with scheduled check-ins in case the outage holds.
- 2026-07-06 14:57 — claude.ai/code web session (same as above): the
  scheduler outage appears OVER — GitHub delivered the morning cron ~3h20m
  late at 14:35 (event=schedule), which ran green end-to-end
  (descript-vs-premiere-pro, youtu.be/4WFuuA-vgd4, pl=ok, IG/FB/TikTok ok)
  but produced a SECOND battle video today: the 12:53 manual dispatch had
  already covered the slot, and the late cron picked battle again off the
  clock (hour<15). Not a bug — expect duplicate-format days whenever a
  slot is covered manually and GitHub later replays the cron. YT repo's
  own Pages builds (unused by the pipeline) still hit the "try again
  later" transient; ignore.
- 2026-07-06 ~15:30 — claude.ai/code web session (same as above): owner
  deleted the duplicate battle Short (descript-vs-premiere-pro,
  youtu.be/4WFuuA-vgd4 now dead — its receipt line in git history is
  expected to 404) because the duplicate hurt the channel's upload flow.
  NOTE: its IG/FB/TikTok crossposts were NOT deleted and are still live.
  Shipped a dedupe guard in publish.yml: a new precheck job skips a
  scheduled run when its cron slot time passed >90 min ago AND a video
  already published after that slot time — so a late-replayed cron can
  never duplicate a covered slot again. Manual dispatches, trigger pushes,
  and merely-late-but-uncovered crons are unaffected.
- 2026-07-06 21:15 — claude.ai/code web session (same as above): covered
  the evening slots during GitHub's all-day scheduler outage (nothing
  scheduled fired again). Blog 20:00 dispatched → gradient-clipping post +
  LinkedIn ok (20:57). YT 20:13 dispatched → comic camera-fright-vs-
  synthesia-pictory live+public (youtu.be/rTTrJmHtQEE), IG/FB/TikTok ok,
  BUT pl=fail: the comic playlist PLU0aizduxfow (created 00:07 today)
  now returns "Playlist not found" — deleted from YouTube during the day.
  Root-cause + fix: create_playlists.py trusted any id already in
  playlists.json without verifying it, so the token-check could never
  self-heal a deleted playlist (would keep reporting exists: the dead id,
  failing every comic upload = 1/3 of videos). Now it verifies each stored
  id via playlists().list and drops+recreates a missing one. Dedupe-guard
  confirmed working in prod: the 18:20 late cron replay of the 16:13 slot
  was SKIPPED (publish job=skipped) because news had already published.
  Minor: publish.yml "Record status" runs audio_qa.py (writes
  last-audio-qa.txt) before its pre-commit `git pull --rebase`, which then
  errors "unstaged changes" (harmless — masked by || true, and the
  post-commit retry loop rebases fine); tidy later by moving the pull
  after the commit.
- 2026-07-08 07:35 — claude.ai/code web session (same as above): DUPLICATE
  comic on 2026-07-07 (burnout-wraith 18:36 + typo-swarm 21:52, both
  fmt=comic; no news for the 16:13 slot). Root cause = format-flip gotcha
  (rule 2) through GitHub's late cron replays: "Pick format by slot" read
  the WALL CLOCK, so the 16:13 news cron replayed at 18:20 picked comic
  (hour 18) instead of news. NOT a dedupe-guard miss (the guard correctly
  skipped the 07-06 21:47 replay; confirmed publish job=skipped). Fix:
  Pick-format now derives the hour from the SCHEDULE cron slot
  (github.event.schedule) for schedule events, not now() — a late replay
  keeps its intended format. Manual dispatch/trigger still use the clock.
  Owner has (or will) delete one of the two 07-07 comics; both their
  IG/FB/TikTok crossposts are live and NOT auto-deleted. NOTE the deeper
  cause is still GitHub's multi-day scheduler outage forcing late replays;
  the external heartbeat remains the real fix.
- 2026-07-08 (later) — claude.ai/code web session (same branch): built the
  EXTERNAL heartbeat (heartbeat/ — Cloudflare Worker) after the owner made
  Claude the operator and approved the plan. It is the only backstop that
  survives a full GitHub scheduler outage (all in-repo backstops are crons
  too). Also added a `format` workflow_dispatch input to publish.yml so the
  Worker (or a manual dispatch) can pin a slot's format — closes the last
  format-flip path for external fires. Owner must mint a fine-grained PAT
  (Actions R/W, both repos) and `wrangler deploy` + `wrangler secret put
  GH_TOKEN` to activate (human-domain). Standing operator calls this session:
  (1) one channel / one format / English, prove before splitting to
  channels or languages; (2) lead format = tool battles; pause news+comic on
  the main channel once the owner is ready (not yet executed — flagged).
- 2026-07-08 ~13:00 — claude.ai/code web session (same branch): heartbeat
  DEPLOYED and LIVE (owner set up the Cloudflare Worker; cron */20 confirmed,
  GH_TOKEN secret works — the Worker URL self-test read the GitHub API and
  correctly reported per-slot status). Deploy went via Cloudflare's "Hello
  World" guided flow (dashboard), not wrangler. From now on missed slots
  self-dispatch; sessions should NOT hand-fire slots unless the Worker is
  down. Note: I mis-diagnosed once mid-setup (claimed the Worker "should have
  fired in the last 93 min" — it had only just been created; owner correctly
  caught it). First real unattended test = whichever slot GitHub next misses.
- 2026-07-08 ~13:10 — claude.ai/code web session (same branch): executed the
  BATTLE-ONLY consolidation (FORMAT_ONLY="battle" in publish.yml Pick-format;
  forces every run — cron/heartbeat/manual — to battle, exits before the
  slot/clock logic, so no heartbeat redeploy needed; one-line revert). Checked
  first: battle topic queue = 13, auto-replenished from a 13-tool roster, so
  3/day is sustainable. Rationale = pre-traction channel, 3 formats fragment
  the algorithm; focus one format (search demand + affiliate fit) then clone
  the winner to a high-income language. News + comic paused (code intact),
  cadence kept at 3/day. Takes effect from the next slot (16:13).
- 2026-07-08 ~17:45 — claude.ai/code web session (same branch): dedupe
  self-check PASSED — the late 11:13 schedule replay (run 28943924318) had
  publish=skipped; the manual battle dispatch published ONE battle
  (midjourney-vs-free-ai-art, pl=ok), no duplicate. BUT found a separate
  over-fire: an extra news video (ai-news-20260708, 15:10) came from the
  self-heal SCHEDULE backstop — GitHub replayed the 12:48 backstop cron late
  (~15:00), its "no publish run in 100 min" heuristic saw the 12:57 battle as
  123 min stale and dispatched publish.yml, which on the pre-battle-only code
  picked news off the 15:00 clock. Fix: RETIRED the self-heal schedule
  backstops (kept the workflow_run failure-retry). The heartbeat supersedes
  them and checks per-slot coverage so it won't over-fire; under battle-only
  an over-fire would have been a duplicate battle. TODO(next): the blog repo
  has the same 08:50/20:50 self-heal backstop, now also redundant with the
  heartbeat — retire it there too.
- 2026-07-08 ~18:10 — claude.ai/code web session (same branch): fixed the
  caption brand-name mishears the owner reported (ChatGPT captioned as
  "Chachi Pt"/"Chachi BT"). Root cause: on the Gemini TTS path, karaoke
  captions were built from Whisper's transcription of the audio
  (_whisper_words), which has no vocabulary context — the ElevenLabs path
  was already correct (uses the provider's char alignment = real script).
  Fix in render_video.py: _align_script_to_timings() keeps Whisper's word
  TIMINGS but substitutes the SCRIPT's spelling (difflib align; drops
  Whisper hallucinations, restores missed words), and _whisper_words now
  passes the script as initial_prompt. Captions now always match the brief.
  3 unit tests added (tests/test_pipeline.py). NOTE per rule 8: eyeball the
  first real Gemini render's captions frame-by-frame to confirm sync — the
  alignment logic is unit-tested but caption timing wasn't visually verified
  in-sandbox (no whisper/audio here).
- 2026-07-10 ~01:00 — claude.ai/code web session (same branch): heartbeat
  is NOT actually dispatching — owner reports every Worker dispatch returns
  403 (reads work: "already covered"/"MISSED" lines render fine). 403 on
  POST /dispatches = the GH_TOKEN PAT lacks Actions WRITE (likely minted
  Read-only) or is expiring. My 2026-07-08 "LIVE" verification only proved
  the READ path — dispatch was never exercised; owner covered all of
  2026-07-09's slots by hand. Fix is human-domain: edit PAT → Actions:
  Read and write, both repos → update GH_TOKEN secret in the Worker.
  Until then sessions must keep covering missed slots. Cloudflare-primary
  cutover (checkpoint 2026-07-12) is blocked on this.
- 2026-07-10 session close — OPEN STATE for next session: (1) BLOCKER —
  heartbeat dispatch returns 403; owner must set the PAT to Actions:Read+write
  (both repos) and update the Worker GH_TOKEN. Until fixed, cover missed slots
  by hand (MCP dispatch publish.yml on main; battle-only forces format). A
  cover check is armed for 11:50 UTC 07-10. (2) Cloudflare-primary cutover
  checkpoint (07-12) is BLOCKED on that token. (3) Battle-only is LIVE
  (FORMAT_ONLY="battle"). (4) Caption fix LIVE (_align_script_to_timings) —
  still eyeball the first Gemini render's caption sync. All 2026-07-09 slots
  published (manual), all battle, pl=ok.
- 2026-07-10 ~14:30 — laptop Claude Code session (direct commit to main):
  diagnosed 2026-07-10's IG+FB crosspost failure. Both 400'd INSTANTLY at
  their first Graph call (IG /media, FB video_reels start) ~0.3s apart while
  staging succeeded and TikTok posted fine — signature of a dead/revoked
  META_PAGE_TOKEN (the only thing IG+FB share; FB's failing call carries no
  video_url so it is not a content/URL problem). Worked 07-03..07-09, died
  ~07-10. Root fix is human-domain: owner re-mints the long-lived
  META_PAGE_TOKEN and updates the secret. Code fix shipped: crosspost.py
  raise_for_status hid the Graph error body (receipts only ever said "400
  Bad Request", never the OAuthException subcode) — added _check() that
  raises WITH r.text, wired into all 5 IG/FB Graph calls, so the next
  failure names the cause (190/463 expired vs 100 param vs permission).
  Also executed the web session's TODO: removed the dead pre-commit `git
  pull --rebase` in publish.yml Record status (audio_qa.py dirties the tree
  right before it, so it always aborted "unstaged changes" — the
  post-commit retry loop is the mechanism that actually rebases). Owner
  reports they regenerated the heartbeat PAT + pasted it on Cloudflare
  today, but today's slot STILL needed a manual run — watch whether
  tomorrow's crons self-fire; if not, the PAT still lacks Actions:write.
- 2026-07-10 ~15:00 — laptop Claude Code session (direct commit to main):
  rebuilt the heartbeat for TRUST after owner said they don't trust it (it had
  failed silently for days). The design (cover-missed-slot) was sound; the gap
  was that a failed dispatch (the 403) was never surfaced and only the READ
  path was ever verified. worker.js now: (1) treats any dispatch != HTTP 204 as
  a failure — logs loudly + pushes to optional NOTIFY_WEBHOOK (Discord/Slack);
  (2) `/?selftest=1` actively PROVES the write path by dispatching the harmless
  idempotent token-check.yml and reporting raw status (204=write ok, 403=PAT
  still read-only, 404=no repo access) — the one check the old version skipped;
  (3) `/` also prints a read-path token-health line. README documents the
  self-test as a required setup step. Owner action: after re-minting the PAT,
  open `<worker-url>/?selftest=1` and confirm it says WRITE OK — that is the
  trust signal. No rewrite of the coverage logic (it demonstrably skipped
  correct replays 07-06..08).
- 2026-07-10 ~17:30 — laptop Claude Code session (same): heartbeat 403 BLOCKER
  RESOLVED. New worker deployed; `/?selftest=1` returned 403 = confirmed the
  PAT still could not dispatch even after the owner "fixed" it. Root cause: the
  fine-grained PAT had been granted **Administration: Read and write** instead
  of **Actions: Read and write** — similar names in GitHub's permission list,
  but workflow_dispatch needs Actions, not Administration (that is why token
  READ worked while dispatch 403'd). Owner switched the permission to Actions:
  R/W; selftest then returned HTTP 204 → WRITE OK. Editing the fine-grained
  token's permission kept its value, so no Cloudflare GH_TOKEN change was
  needed. Operational facts for next session: worker HTTP host is
  `wispy-tooth-238cpipeline-heartbeat.dani-malik507.workers.dev` (quick-create
  auto-prefixed the name; the bare `pipeline-heartbeat.<sub>` host 404s);
  `/?selftest=1` proves write, `/` shows per-slot coverage + token health.
  Also this session: IG+FB crosspost was a dead META_PAGE_TOKEN — re-minted a
  never-expiring Page token (verified live, ig=ok/fb=ok on two runs). Both
  blockers that had forced manual slot-covering are now closed; the heartbeat
  should auto-cover missed slots unattended from here.
- 2026-07-10 ~20:50 — laptop Claude Code session (direct commit to main):
  20:13 comic slot missed by GitHub's cron (routine skip). Heartbeat was NOT
  broken — the slot was only 33min old (< GRACE_MIN=35), so its "outside
  window" line was the grace hold, not abandonment; it would have auto-covered
  at the 21:00 tick. I hand-fired it early at 20:47 anyway (battle, per
  FORMAT_ONLY) — preempted the heartbeat's first real unattended test; no dupe
  (heartbeat sees the 20:47 run as "already covered"). Per owner request, shifted
  the publish crons from :13 to :59 of the prior hour (11:13→10:59, 16:13→15:59,
  20:13→19:59 UTC) and synced heartbeat/worker.js SLOTS to match. I flagged that
  the minute won't fix GitHub's flakiness (the heartbeat does) and :59 sits just
  before GitHub's :00 peak; owner chose :59. ACTION PENDING (human-domain): the
  Worker must be REDEPLOYED for the new SLOT times to take effect — until then
  the Worker still watches the old :13 slots and would over-fire/miss.
- 2026-07-10 ~21:30 — laptop Claude Code session (direct commit to main):
  PERFORMANCE AUDIT (owner reports IG skip 80-90%, YT ~30 views/video; owner
  asked Claude to lead the channel as its own). Root cause found IN THE PROMPT:
  BATTLE_BULLETS mandated "segment 1 = the hook plus a one-line setup of the
  matchup", so every video opened with ~8-10s of "Today we pit X against Y"
  over a static VS card (intro scene length = segment-1 audio length). The
  swipe decision happens in ~1.5s. Fix shipped: segment 1 = ONLY the hook
  (max 12 words, one surprising concrete claim/result, matchup never spoken;
  intro shrinks to ~3s automatically since scenes are audio-driven); tagline
  = the claim as big card text (was "a question of 8 words"); all hooks must
  carry a concrete specific (number/time/price/result). Hook-style A/B
  rotation preserved. 26/26 tests pass. MEASUREMENT PLAN: 10-15 videos on the
  new hooks (~5 days), primary metric = IG skip rate; if still >80% the
  FORMAT is dead (text-card battles = search content in an entertainment
  feed, no visual payoff) and the play is a format pivot, NOT more polish.
  Kill/pivot decision pulled forward from 2026-08-18 to ~2026-07-16.
- 2026-07-10 ~21:45 — laptop Claude Code session (same, direct commit to
  main): LENGTH CUT, second lever on completion. Battles now EXACTLY 2
  rounds (was model's choice of 2-3 → 59-90s videos; text-card Shorts that
  long don't get finished, and completion % is the feed's primary ranking
  input), round narration max 30 words (was 35), final segment = verdict +
  one comment question, max 25 words, follow-nudge REMOVED (a nudge at 30
  views converts nobody and costs retention). Target runtime ~40-50s.
  Validator still accepts 2-3 rounds as fallback. Both levers (hook + length)
  aim at the same metric so the 07-16 IG-skip read stays clean. Rule-8 note:
  EYEBALL the first new-style render (short intro + claim card + 2 rounds)
  frame-by-frame after the 10:59 run.
- 2026-07-10 ~22:30 — laptop Claude Code session (direct commit to main):
  RANKING FORMAT SHIPPED (owner pasted the niche SERP; market read: "X vs Y"
  Shorts cluster at <100-80k views even from established channels, while
  Top-5/tier-list/free-vs-paid ranking Shorts repeatedly hit 0.9M-2.5M, and
  they're MORE affiliate-aligned). New RankingShort composition
  (remotion/src/ranking/, reuses battle fx + sceneFrames contract),
  FORMAT=ranking in generate_brief.py (_clean_ranking: exactly 5 items in
  5..1 countdown order, 7 narration segments, hook-only seg 1; own topic
  queue ranking_queue/ranking_published in topics.json with proven-angle
  replenish), render_ranking() via the shared _render_scenes, playlist "AI
  Tool Rankings", publish.yml slot map: <15 UTC battle else ranking (=10:59
  battle control, 15:59+19:59 ranking; battle-only FORMAT_ONLY removed;
  news/comic reachable only by explicit format= override), heartbeat SLOTS
  mirror the split (OWNER MUST REDEPLOY the Worker again). 31/31 tests.
  07-16 checkpoint now reads battle-vs-ranking head-to-head on IG skip.
  Rule 8: first ranking render reviewed frame-by-frame before approval.
