# Snackbyte AI — YouTube automation pipeline

Faceless YouTube Shorts channel, 3 videos/day, ~$0/mo, fully automated via
GitHub Actions. This file is the ops runbook: any Claude session (laptop,
claude.ai/code, mobile) should read it before touching anything.

## Operating agreement (owner ↔ Claude — set 2026-07-08, UPGRADED 2026-07-11)

**2026-07-11: the owner made Claude the LEADER of this project. Claude
decides EVERYTHING — theme, visuals, tone, topics, niche, formats,
schedule, strategy. If a change is needed, make it and ship it. Do not
present options, do not ask permission for content/engineering/strategy
calls, do not wait for sign-off. Decide, execute, log it here, tell the
owner after.** The honest boundaries that survive:

- **Decisions still need evidence.** Data first (receipts, SERP/market
  reads, analytics), then act. Leadership is not license for whims — the
  kill/scale checkpoints still gate big bets.
- **Claude disagrees openly.** When the owner proposes something Claude
  thinks is a mistake, argue it plainly and don't cave to please. Do not
  rubber-stamp.
- **The owner can overrule after the fact.** It is their Google account,
  affiliate revenue, and name — they carry every consequence. Claude will
  not pre-commit to overriding the owner against their will.
- **Human-domain actions stay the owner's** (Claude physically cannot
  execute them): minting tokens, secrets, billing/quota, creating
  Google/YouTube accounts, deleting published videos, TikTok/Meta account
  actions, Cloudflare Worker deploys. Escalate these; decide everything
  else.
- **Keep replies TERSE** (owner ask, 2026-07-08). Answer, state the action,
  done. No walls of text, no restating what the owner knows, no option
  menus. Brevity conserves the owner's tokens.

## Architecture (one video = one publish run)

`publish.yml` — **NO GitHub crons (2026-07-11): the Cloudflare heartbeat
Worker is the SINGLE firing source.** It dispatches at 10:59 / 15:59 / 19:59
UTC (= 11:59/16:59/20:59 UK BST) and retries via :20/:40 sweeps; slot times
live in `heartbeat/wrangler.toml` + `worker.js` SLOTS. GitHub's scheduler
(late fires + hours-late replays racing the Worker) double-published 3 slots
in 36h — do not re-add `schedule:` crons.
1. **Pick format by slot** — UTC hour <15 battle, else ranking (news/comic
   paused; reachable only by explicit `format=` override). Worker dispatches
   land at the exact slot minute, so clock-derive is always right.
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
- **`heartbeat/` (Cloudflare Worker) — THE SCHEDULER since 2026-07-11** (was
  a backstop; promoted to sole firing source when cron-vs-Worker races
  double-published 3 slots). Cron triggers at the exact slot minutes dispatch
  immediately; `20,40 * * * *` sweeps retry any still-uncovered slot (never
  younger than MIN_RETRY_MIN=10, so a fresh dispatch can't be double-fired);
  every dispatch is preceded by a runs-API coverage check (idempotent ticks).
  No format pins — publish.yml's slot map is the single format source.
  Secret `GH_TOKEN` = fine-grained PAT, **Actions R/W** both repos;
  deploy/rotate is human-domain (see `heartbeat/README.md`; prefer `wrangler
  deploy` — dashboard pastes drifted 3x). `/?selftest=1` proves the write
  path; `/` is a read-only status page. If the Worker dies NOTHING publishes
  (by design); watchdog.yml + stale receipts are the alarm.

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
11. **ONE firing source.** Never re-add `schedule:` crons to publish.yml or
    auto-blog.yml — GitHub crons racing the heartbeat Worker double-published
    3 slots in 36h (2026-07-10/11). The Worker is the scheduler; GitHub crons
    survive only in alarms/low-stakes workflows (watchdog, tests, research).

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

**FORMAT STATE (2026-07-11): battle (10:59 slot, control) vs ranking
(15:59 + 19:59), head-to-head on IG skip rate.** News + comic are PAUSED,
not deleted (code intact; explicit `format=` override reaches them).
**CHANGE FREEZE from 2026-07-12: no format/visual/voice/engine changes
until the checkpoint read (~2026-07-19, 7 clean days) — quality-gate and
dedupe fixes only.** The 07-10/11 burst (hook surgery, length cut, ranking
v1→v3, voice/pace changes) stacked too many variables to attribute
anything; the freeze buys a clean read. Plan after a winner: clone it to a
high-income language (DE/FR/ES) reusing the engine — NOT new niches. Do not
split channels/languages before one format proves out.

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
  FIRST RANKING VIDEO VERIFIED LIVE same night: youtu.be/q4Xy0zJRalo
  (top-free-ai-writing-tools, 48s, wer 0.14, pl=ok new "AI Tool Rankings"
  playlist, IG+FB+TikTok ok); frames reviewed, approved. VOICE PINNED
  (owner pick): repo var GEMINI_VOICE=Puck (the voice random.Random(slug)
  chose for descript-vs-davinci-resolve-speed; owner liked it). No
  GEMINI_STYLE var set, so code falls back to Puck's roster style (excited
  sports commentator). Roster rotation OFF until the var is deleted.
- 2026-07-11 ~01:00 — laptop Claude Code session (direct commit to main):
  RANKING V2 after owner REJECTED the first ranking video (all of: bland/
  repetitive text-only scenes, no real tool visuals, voice, and "wanted to
  skip at the very beginning" — hook failed). Diagnosis: (a) spoken opener
  was "Five free AI tools." — a dull count the prompt didn't forbid; (b)
  scenes were 5 near-identical text cards; (c) voice was Aoede — that video
  rendered 10 min BEFORE the Puck pin, so voice is already fixed. Shipped:
  _stage_ranking_media() in render_video.py fetches a portrait Pexels PHOTO
  per scene (new pexels_photo(); Ken Burns zoom + dark overlay in the
  composition via new SceneBg) and real tool favicons via Google
  s2/favicons (>500-byte guard drops the generic globe; nominative use,
  white-chip presentation) shown on rank cards + outro rows; all
  best-effort with gradient/text-only fallbacks. RANKING_BULLETS now bans
  count/theme-restatement openers with GOOD/BAD examples. public/ranking
  gitignored (staged fresh each render). Stills verified locally with
  staged media (intro wiring initially missed — whitespace-failed replace;
  caught by byte-identical still, fixed). 31/31 tests. Rule 8: review the
  first CI-rendered v2 ranking frames (15:59 slot or render-trigger).
- 2026-07-11 ~12:30 — laptop Claude Code session (direct commit to main):
  DUPLICATE at the 10:59 slot: cron replayed 50 min late (11:42, inside
  precheck's <=90-min allowance) AFTER a heartbeat cover at 11:40 (grace
  35 min) — the 35..90-min window let both fire. AND the dispatch shipped
  a RANKING into the battle slot: the deployed Worker's SLOTS format had
  drifted (third dashboard-paste drift in 24h). Fixes: (1) worker SLOTS no
  longer carry format at all — publish.yml's slot map is the single source
  of truth, and with 2 formats (boundary 15:00) no cover window inside
  CUTOFF_MIN=165 crosses a boundary, so clock-derive is always right;
  (2) GRACE_MIN 35 -> 100 (past precheck's 90-min threshold: a <=90-min
  late cron runs alone, a covered slot's later replay gets skipped).
  Owner asked to delete the wrong-format duplicate
  (best-ai-voice-generators-podcasters, youtu.be/83iKr8i-oRQ; its IG/FB/
  TikTok crossposts too). OPEN: owner reports BOTH of today's videos'
  audio "sounded so bad" despite clean QA numbers (Puck, wer 0.03->0.10);
  awaiting specifics (rushed/robotic/choppy/mispronounced) before a TTS
  fix — do not guess-tune voice settings blind.
- 2026-07-11 ~12:50 — laptop Claude Code session (same): AUDIO DIAGNOSED
  (owner: "rushed + overacted/shouty"; liked the DaVinci render). Same
  voice (Puck) + same style prompt on both — the delta is the 07-10 length
  cut: short punchy segments + a style prompt literally saying "fast and
  punchy" makes Gemini sprint and shout; long segments gave it room.
  Fixes: Puck roster style -> "lively sports commentator, clear and
  unhurried, pausing briefly after each sentence"; audio_qa.py new
  pace=X.XXwps metric (script words / spoken audio seconds; >3.0 RUSHED,
  >2.7 brisk, else natural — ADVISORY only). Verify pace + owner ear-test
  on the 15:59 ranking. If still rushed: next levers are GEMINI_STYLE var
  iteration or ffmpeg atempo ~0.95 on narration. PACING FIX VERIFIED in a
  render-only test: pace=2.20wps(natural), 48s vs the rushed 40s original.
- 2026-07-11 ~13:40 — laptop Claude Code session (same): RANKING V3
  (owner: Pexels backgrounds made videos DULLER; videos not grabbing
  attention). Redesign shipped (fa2bb36): vivid per-rank gradient worlds
  (sky/violet/orange/pink/gold; dark navy dropped), white name pill +
  favicon + tag chip, and the tool's REAL homepage screenshot (WordPress
  mshots API, free, no key: s0.wp.com/mshots/v1/<urlencoded>?w=720&h=1280,
  first call warms cache -> poll until >15KB) in a floating tilted
  phone-frame with slow scroll-pan. Blankness guard _shot_richness():
  grayscale stddev of downscaled shot < 20 = bot wall (Cloudflare verify:
  chatgpt 5.7, gemini 10.9) -> dropped; real pages measure 36+; no-shot
  fallback layout = bigger pill + reason, still vivid. Pexels photo path
  REMOVED from ranking (pexels_photo deleted). Local stills verified all
  scene types incl fallback. NOTE: the 13:0x render-trigger re-rendered
  the battle brief (latest.txt) — ignore; first real v3 = 15:59 slot,
  frame-review it (rule 8).
- 2026-07-11 ~20:50 — laptop Claude Code session (same): VOICE ROOT CAUSE
  finally measured (owner: 15:59 video still not the DaVinci sound).
  DaVinci = 181 words / 5 segments = 36 w/seg at ~2.8wps: FAST but
  FLOWING. Today's ranking = 114 words / 7 segments = 16 w/seg at 2.11:
  slow AND choppy. Segment length IS the voice: 7 tiny TTS calls = 7
  disconnected reads each restarting energy; no style prompt fixes that.
  Shipped: Puck style restored to the EXACT DaVinci prompt ("excited
  sports commentator, fast and punchy"), ranking item segments 22 -> 26-34
  words (2-3 flowing sentences), battle rounds 30 -> 28-36 words. Expect
  ~60-70s videos again; pace target ~2.6-2.9wps. ALSO: 19:59 cron missed
  by GitHub AGAIN; my 20:39 curl of the Worker / endpoint triggered its
  cover dispatch (ranking, correct). Deployed Worker = STALE (format pins
  visible, GRACE 35): owner has NOT done the final redeploy — DUPLICATE
  WINDOW OPEN tonight if the cron replays 35-90 min late; watch for a
  second 19:59 video. Owner also still to delete the morning duplicate
  (youtu.be/83iKr8i-oRQ).
- 2026-07-11 ~21:15 — laptop Claude Code session (same): DEDUPE REDESIGN
  after owner asked why the 19:59 cover took ~an hour (35-min grace + 20-min
  tick + 10-min render, by design — and my pending GRACE=100 would have made
  it ~2h). publish.yml precheck now skips a scheduled run whenever ANY other
  publish run was created at/after its slot time (runs-API check, id != self;
  deterministic, no timing window) — replaces the ">90 min late AND video
  published" heuristic. Worker GRACE_MIN 100 -> 20: missed slots covered
  20-40 min after slot time, duplicates structurally impossible. ALSO / is
  now READ-ONLY (a status curl at 20:39 had beaten the 20:40 cron tick to
  the dispatch — monitoring must not mutate; only the scheduled tick
  covers). Worker redeploy STILL PENDING (owner) and now carries: no format
  pins + read-only / + GRACE 20.
- 2026-07-11 ~23:50 — laptop Claude Code session (direct commit to main):
  SINGLE-FIRING-SOURCE CUTOVER (owner: "if GitHub cron is not reliable why
  let it fire the pipeline anyway? why not one source?" — correct). Tonight
  the 19:59 slot DOUBLE-PUBLISHED again: heartbeat cover 20:39 shipped
  free-jasper-alternatives-copywriting (youtu.be/jOQx01hG2wg) AND the 20:51
  late cron replay shipped top-ai-tools-small-business
  (youtu.be/bRBond0gT8s) — the replay started 21 min before the
  deterministic precheck landed (21:12). Both crossposted to IG/FB/TikTok.
  Fix = remove the race, not patch it again: `schedule:` crons DELETED from
  publish.yml AND auto-blog.yml; the Worker is now THE scheduler — cron
  triggers at exact slot minutes (59 10,15,19 / 0 8,20) dispatch
  immediately, a 20,40 sweep retries uncovered slots (MIN_RETRY_MIN=10
  guards the runs-API lag window; coverage check before every dispatch =
  idempotent). Prechecks kept as dead-code safety nets. Blog repo also got
  the precheck ported + its 08:50/20:50 self-heal backstops retired
  (77f8d4e — it had been double-posting every slot since the Worker's write
  path came alive). PACE GATE shipped: _pace() from take word timings;
  takes >3.05wps retake once and lose up to 3 score points (published video
  tonight measured 3.36wps RUSHED even after the DaVinci-conditions prompt
  fix — the prompt doesn't hold pace; the gate must). 35/35 tests.
  TRANSITIONAL STATE until owner redeploys: stale deployed Worker (*/20
  tick, GRACE 35) still covers all slots ~35-55 min late with correct
  formats, and with repo crons gone there is NO dupe window — safe, just
  late. OWNER ACTIONS: (1) `wrangler deploy` from heartbeat/ (or dashboard:
  paste worker.js + set the THREE crons from wrangler.toml), then
  /?selftest=1 -> WRITE OK; (2) delete ONE of tonight's pair — recommend
  deleting free-jasper (jOQx01hG2wg, pre-pacing-fix code) and its IG/FB/TT
  crossposts — plus the morning duplicate youtu.be/83iKr8i-oRQ still
  pending; (3) optionally prune the 3 duplicate blog posts' LinkedIn
  shares. CHANGE FREEZE declared: no format/visual/voice/engine work until
  the ~07-19 read; gates and dedupe only.
- 2026-07-13 — laptop Claude Code session (direct commit to main): owner
  OVERRODE the freeze on the 3 open ranking-quality complaints (owner taste
  rejection is a valid override). All three shipped: (1) SCREENSHOTS no
  longer cropped — RankingVideo ScreenshotCard was a 560x780 frame with a
  scroll-pan that cut the top+bottom off every 720x1280 shot; replaced with
  a 636x1120 (9:16) frame + object-fit:contain, so the WHOLE capture shows,
  no pan. (2) RANKING TEMPLATE rebuilt — the 5 per-rank rainbow "worlds" of
  v3 (owner: not eye-catching) are gone; new cohesive dark "tech editorial"
  look: near-black base + ONE saturated brand accent per video (hashed from
  theme, varies video-to-video, consistent within one), giant ghost rank
  numeral as a design element, screenshot as the dominant hero. Stills
  reviewed frame-by-frame (intro / no-shot / with-shot) — clean. (3) VOICE
  pitch drift between sections FIXED at the root — single-voice formats
  (battle/ranking/news) now record the WHOLE script in ONE Gemini TTS call
  (_voice_single_pass) then slice per scene at word-gap midpoints, so the
  voice holds one pitch across the video instead of restarting energy on 5-7
  tiny per-scene calls; also cuts free-tier usage to 1 TTS request/video.
  Comics keep per-hero voices (per-scene path). Safe fallback to the
  per-scene loop if single-pass timings fail. 35/35 tests; render_video
  syntax ok; TSX compiles (remotion still). Rule 8: eyeball the first CI
  ranking render's audio + screenshot frames after the next 15:59/19:59 slot.
- 2026-07-14 — laptop Claude Code session (direct commit to main): PROPER
  16:9 HOOK THUMBNAILS (owner: "why no thumbnails" → confirmed via live
  maxresdefault that custom thumbs WERE set, but the old step grabbed a 9:16
  video frame that YouTube letterboxed into 16:9 with blur bars; and the
  Shorts feed ignores custom thumbnails entirely — platform limit, only the
  watch page / search / shares use them). New remotion/src/thumb/Thumb.tsx
  composition (1280x720, registered id "Thumb") renders an edge-to-edge hook
  card per format: ranking = TOP-N accent chip + big theme + real favicon
  strip; battle = "A VS B" with name auto-sizing so long names ("Premiere
  Pro") don't clip + tagline; news = "AI NEWS" chip + headline; comic = "AI
  TOOLVERSE" + title. Same dark single-accent identity as the new ranking
  template (accent hashed from title). render_video step 6 now renders the
  Thumb still via _thumb_props(brief, props) into OUT/<slug>.jpg (what
  upload_video already uploads), old frame-grab kept as fallback so a run
  never ships thumbless. All 4 thumb types reviewed frame-by-frame; 35/35
  tests. Does NOT change the Shorts-feed appearance (YouTube frames those) —
  upgrades every 16:9 surface.
- 2026-07-14 — laptop Claude Code session (direct commit to main): RANKING
  FORMAT REPLANNED, screenshots dropped for good (owner: "don't add app
  previews, replan"). Diagnosed why app screenshots never worked: mshots
  ignores h= and returns ~4:3 (720x960) or, at desktop width, 16:10 landscape
  — a wide desktop homepage can't fill a portrait 9:16 scene without letterbox
  or side-cropping the hero text (the "landscape in portrait / cropped"
  complaint). No free service gives a true 9:16. Rather than keep fighting it,
  removed screenshots entirely (deleted _download_shot/_shot_ok/_shot_richness;
  _stage_ranking_media now stages only favicons; shots prop gone). New ranking
  format = pure TYPOGRAPHIC countdown per the remotion video-layout rule (one
  focal point, big text, reveal over time): giant ghost rank numeral backdrop,
  #N pill, huge tool NAME as the focal element with a favicon-or-letter-
  monogram brand cue (never blank), one accent tag chip, reason hook, a top
  countdown rail (game-show momentum), SparkBurst on reveal + Confetti on #1,
  cohesive single accent per video. Stills reviewed (rank #5 + winner #1) —
  clean, kinetic, no clutter. ALSO voice: VOICE_SPEED 1.15 -> 1.0 (owner heard
  the 15% atempo speed-up as fast/"pitched"; atempo now skipped at 1.0). Used
  the youtube-automation:remotion-best-practices skill (video-layout rule) to
  guide the redesign. 35/35 tests. Rule 8: frame-review the first CI render.
- 2026-07-14 (later) — laptop Claude Code session: the first typographic
  redesign read "okayish" to the owner. Rather than guess again (4th taste
  miss), rendered 3 distinct style DIRECTIONS as stills (Bold / Glass-Neon /
  Poster) via a throwaway StyleDemo composition and had the owner pick.
  IMPORTANT UX NOTE: the owner is on the CLI and does NOT see inline images —
  deliver visual previews by writing the file to D:\Linkedin\ and opening it
  with PowerShell Invoke-Item (mp4s and a PIL-built compare PNG). Owner liked
  Bold + Poster → shipped a fusion "BOLD POSTER" (commit 4b4eb79): vivid
  saturated per-video bg, GIANT hot-yellow black-outlined rank numeral bleeding
  off the TOP-RIGHT corner (poster graphic — NOT centered; owner explicitly
  wanted the corner-bleed, rejected the fully-centered contained version),
  black bottom color-block with tool name + favicon/monogram + red tag chip +
  reason, #1 flips block to yellow + confetti. Approved after a music preview.
  Local preview caveat: no TTS keys on the laptop (CI-only), so local previews
  are music-only — muxed via Remotion's BUNDLED ffmpeg
  (node_modules/@remotion/compositor-win32-x64-msvc/ffmpeg.exe; it's a stripped
  build — no afade filter, volume works). Rule 8: frame-review first CI render.
  FOLLOW-UP (not done): the ranking Thumb card still uses the older dark
  single-accent look — align it to bold-poster if the owner wants thumbnail
  consistency.
- 2026-07-16 — laptop Claude Code session (direct commit to main): health
  sweep all green (all 5 slots fired on time via the Worker, receipts clean,
  no open issues, IG/FB/TikTok ok, blog + LinkedIn ok). Executed the pending
  rule-8 frame review of the first CI bold-poster ranking render
  (free-ai-synthesia-alternatives, youtu.be/GI4R9U5vO04): layout, corner
  numeral, chips, confetti, outro all correct — but the burned-in karaoke
  captions (Cap style MarginV 360 = bottom y1560) land INSIDE the bold-poster
  bottom info block (top y1160) and overlap the reason text on every rank
  scene (illegible double-text). Fix: per-Dialogue MarginV override in
  build_karaoke_ass/build_ass_at (_margin_at windows); _render_scenes gains
  lift_captions applied to MID scenes only; render_ranking passes 830 so
  rank-scene captions sit just above the block while intro/outro keep 360
  (their card layouts need the low position). Legibility-defect fix, same
  freeze-exception class as the 07-13 crop fix — not a style change. 37/37
  tests (2 new). Rule 8: spot-check captions on the next 15:59/19:59 ranking
  render. Audio single-pass verified working in the same video (one
  continuous read, pace 2.97wps brisk, wer 0.05).
- 2026-07-16 (later) — laptop Claude Code session (direct commit to main):
  owner reported scene-boundary voice artifact on the single-pass read: "it
  sounds like it was about to say the word of the next scene... and stops."
  Root cause in _voice_single_pass: scene clips were cut at the MIDPOINT of
  the inter-scene word gap, so every clip kept the front half of the pause —
  breath intake plus the pre-voicing of the next scene's first word (Whisper
  start timestamps miss the true onset), then the scene's 0.8s visual tail
  held that cut-off syllable in silence. Fix: new pure helper
  _scene_cut_points — cuts hug the scene's own words (tail CUT_TAIL_S=0.12s
  after last word, lead CUT_LEAD_S=0.10s before first word, each capped at
  30% of the gap so tiny gaps can't overlap; negative-gap drift clamps to
  the word edge), mid-gap audio dropped; plus 15ms fade-in / 60ms fade-out
  per clip so the cuts can't click (afade = CI ffmpeg only, same as the mux;
  single-pass never runs locally since TTS keys are CI-only). 41/41 tests
  (4 new on the cut math). Owner-reported defect = freeze exception. Rule 8:
  ear-check scene transitions on the next ranking render (10:59 or 15:59).
- 2026-07-16 (night) — laptop Claude Code session (direct commit to main):
  FIRST BREAKOUT ANALYZED. Owner flagged "I Ranked 50 AI Tools for YouTube,
  Only 5 Are Worth It" (ai-tools-for-youtube, 07-15, hook=result_first) at
  214 views; channel RSS confirms every sibling video sits at 0-35 (second
  best 35, most <10) on identical production. The winner is the ONLY video
  that (a) targets CREATORS — an audience natively on YouTube with a huge
  recommender interest cluster (all other topics target off-platform
  audiences: students, e-commerce, sales, freelancers) — and (b) uses
  first-person effort+survivor title framing ("I Ranked 50..., Only 5 Are
  Worth It") vs commodity listicle phrasing everywhere else. Topic strategy
  shipped (topics = demand-side work, explicitly outside the freeze; battle
  queue untouched as the experiment's control): 6 creator-audience topics in
  the champion formula front-loaded into ranking_queue (faceless channels,
  thumbnails, Shorts, TikTok, podcasters, video creators);
  replenish_rankings prompt now cites the channel's own 214-vs-10 data and
  asks ~half of new ideas in that pattern; title guidance keeps first-person
  topics verbatim. topics.json edited via Python (PowerShell ConvertTo-Json
  writes a BOM that would crash the CI loader — got caught, redone).
  Dispatched weekly-research.yml for fresh retention/trend data. VERIFY:
  next ranking slots run the champion-formula topics — watch their views
  vs the 07-15 baseline; fold into the ~07-19 checkpoint read.
- 2026-07-16 (night, later) — laptop Claude Code session (direct commit to
  main): CROWN-VS-VERDICT BUG (owner asked how a 2-round battle picks its
  winner on a 1-1 split — the answer exposed a shipped defect). The spoken
  verdict is the model's free judgment and may name either tool, but
  VerdictScene computed the on-screen crown from the round score with
  `final.a >= final.b` — a 1-1 split ALWAYS crowned toolA. 5 of the 6
  two-round battles since the length cut split 1-1, and 2 shipped with the
  crown contradicting the voice: writesonic-vs-copy-ai-sales-emails (07-13,
  voice says Copy.ai) and synthesia-vs-heygen-training-videos (07-16, voice
  says HeyGen). Fix: battle block gains REQUIRED-by-prompt "champion":
  "a"|"b" (the model judges the match); _clean_battle validates it and for
  old/missing values derives it (majority of rounds; on a split, the tool
  named FIRST in the verdict — every observed split verdict opens "X wins";
  toolA last resort); VerdictScene crowns props.champion, score kept only
  as legacy fallback. 45/45 tests (4 new), tsc clean. Correctness fix =
  freeze exception. Owner may want to delete/ignore the two contradicting
  videos (both low-view; probably not worth the churn). Rule 8: eyeball the
  next battle render's verdict scene (10:59 slot).
- 2026-07-17 — laptop Claude Code session (direct commit to main): PUBLISH
  FAILURE (owner flagged "error with 3 attempts to publish" + "self-heal
  error"). Root cause: the "Save brief" git step hit a merge conflict in
  automation/latest.txt (two publish runs raced — both pass the precheck
  while in-flight since neither has published yet, then collide writing
  latest.txt), and the retry loop could not recover: `git pull --rebase`
  left a half-finished rebase whose "unmerged files" state failed all 3
  retries. Both today's 10:59 attempts (11:06 + an 11:34 self-heal rerun on
  the pre-fix workflow) died the same way; self-heal correctly escalated =
  issue #16 (that is self-heal WORKING, not a self-heal bug). Fix: both push
  loops (Save brief + Record status) now `git pull --rebase -X theirs` (keeps
  THIS run's pointer/ledger files — latest.txt/topics.json/universe.json —
  unique brief filenames never conflict) and `git rebase --abort` any stuck
  rebase before retrying; bumped 3→5 attempts. Ported the identical fix to
  the blog repo's auto-blog.yml (both loops). Re-dispatched publish on the
  fixed code to cover today's slot. The -X theirs makes concurrent runs
  last-writer-wins instead of deadlocking; a full mutex was judged overkill.
  NOTE my own frequent pushes to main during a session also widen this race
  window — avoid pushing while a publish run is mid-flight (rule 9).
