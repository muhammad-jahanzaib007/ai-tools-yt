# Pipeline heartbeat (Cloudflare Worker) — THE scheduler

**Since 2026-07-11 this Worker is the ONLY thing that fires the pipelines on a
schedule.** Both repos' workflows have NO `schedule:` crons any more. GitHub's
cron scheduler fires late, replays runs hours later, and skips whole days;
running it alongside this Worker meant two firing sources racing each other,
which double-published 3 slots in 36 hours (2026-07-10/11) despite dedupe
patches. One source, no race.

It schedules **both** repos:
- `ai-tools-yt` → `publish.yml` (10:59, 15:59, 19:59 UTC)
- `muhammad-jahanzaib007.github.io` → `auto-blog.yml` (08:00, 20:00 UTC)

## How it works

Cloudflare cron triggers (see `wrangler.toml`, exactly 3 — the free-plan cap):

1. `59 10,15,19 * * *` — YT slot minutes: dispatch `publish.yml` immediately.
2. `0 8,20 * * *` — blog slot minutes: dispatch `auto-blog.yml` immediately.
3. `20,40 * * * *` — retry sweeps: any slot that is still uncovered (failed
   dispatch, Cloudflare hiccup) gets re-dispatched — but only once the slot is
   `MIN_RETRY_MIN` (10 min) old, so a just-dispatched run whose row hasn't
   appeared in GitHub's runs API yet can never be double-fired.

Before EVERY dispatch the Worker checks GitHub's runs API: a slot with any run
created at/after its slot time is "covered" and is never fired again. Every
tick is idempotent.

Formats are NOT pinned here — `publish.yml`'s "Pick format by slot" derives
the format from the clock, and no age inside `CUTOFF_MIN` (165 min) crosses
the 15:00 format boundary. Slot times live in TWO places that must match:
`SLOTS` in `worker.js` and the slot-minute crons in `wrangler.toml`.

**If this Worker dies, nothing publishes — by design (one source).** The
alarms for that: `watchdog.yml` (GitHub cron, daily upload-freshness check
≤26h) and the `.github/last-*.txt` receipts going stale.

## Trust model

An earlier version failed **silently** for days: its dispatch POST returned
403 (the PAT had "Administration" instead of "Actions" permission) and nothing
surfaced it, because only the read path was ever exercised. Now:

1. Any dispatch that is **not HTTP 204** is a failure — logged loudly and
   pushed to `NOTIFY_WEBHOOK` if set.
2. **Write-path self-test**: `https://<worker-url>/?selftest=1` dispatches the
   harmless idempotent `token-check.yml` and prints the raw status —
   **204 = write works**, 403 = PAT lacks Actions:write, 404 = no repo access.
   Run it after every token or deploy change.
3. `https://<worker-url>/` prints per-slot coverage + token health.
   **Read-only** — it never dispatches (a status curl once fired a slot).

## Deploy / update (owner — human-domain)

Prefer wrangler over dashboard pasting — three dashboard-paste drifts in 24h
(2026-07-10/11) shipped stale slot maps:

```bash
cd heartbeat
npm i -g wrangler          # once
wrangler login             # once
wrangler deploy            # ships worker.js AND the cron triggers together
wrangler secret put GH_TOKEN   # only when the PAT rotates
```

Dashboard route (if wrangler is unavailable): paste the CURRENT `worker.js`,
then set the THREE cron triggers from `wrangler.toml` by hand, then open
`/?selftest=1` and confirm `WRITE OK`.

PAT requirements: fine-grained, **both** repos, permission **Actions: Read
and write** (NOT "Administration" — similar name, wrong permission, cost days).

## Notes

- `?selftest=1` fires a real (harmless, idempotent) run each time.
- To change slot times: edit `SLOTS` in `worker.js` AND the crons in
  `wrangler.toml`, then `wrangler deploy`.
