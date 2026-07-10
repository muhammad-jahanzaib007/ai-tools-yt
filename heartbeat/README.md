# Pipeline heartbeat (Cloudflare Worker)

External watchdog for both pipelines. GitHub's cron scheduler has skipped runs
for days at a time; every in-repo backstop is *also* a GitHub cron, so it dies
in the same outage. This Worker runs on Cloudflare — outside GitHub — and
re-fires any publish/blog slot that GitHub failed to run.

It covers **both** repos:
- `muhammad-jahanzaib007.github.io` → `auto-blog.yml` (08:00, 20:00 UTC)
- `ai-tools-yt` → `publish.yml` (11:13 battle, 16:13 news, 20:13 comic UTC)

## How it works

Every 20 min the Worker checks, for each slot whose time passed 35–165 min ago,
whether a run of that workflow was created after the slot time. If none was, it
fires `workflow_dispatch`. YT slots pass an explicit `format`, so a late fire
can't flip the format off the wall clock. GitHub replaying the same cron later
is harmless — `publish.yml`'s dedupe precheck skips the replay because a video
already published.

## Trust model (why you can believe it now)

The previous version failed **silently** for days: its dispatch POST returned
403 (the PAT lacked "Actions: write") and nothing surfaced it, because only the
read path (listing runs) was ever exercised. This version:

1. Treats any dispatch that is **not HTTP 204** as a failure — logged loudly and
   pushed to `NOTIFY_WEBHOOK` if set. A silent 403 can no longer hide.
2. Ships a **write-path self-test** you can run in a browser any time:
   `https://<worker-url>/?selftest=1` dispatches a harmless idempotent workflow
   (YT `token-check.yml`) and prints the raw status —
   **204 = write works**, 403 = PAT still read-only, 404 = token can't see repo.
   Run it after every token change.
3. `https://<worker-url>/` prints per-slot coverage **plus** a read-path token
   health line.

## One-time setup (owner — human-domain)

1. **Mint a GitHub fine-grained PAT** (github.com → Settings → Developer
   settings → Fine-grained tokens):
   - Resource owner: `muhammad-jahanzaib007`
   - Repository access: **both** `ai-tools-yt` and `muhammad-jahanzaib007.github.io`
   - Permissions: **Actions → Read and write** (that's all it needs)
   - Copy the token (starts `github_pat_...`).

2. **Deploy the Worker** (from this `heartbeat/` directory):
   ```bash
   npm i -g wrangler        # if not installed
   wrangler login           # opens your Cloudflare account
   wrangler deploy
   wrangler secret put GH_TOKEN   # paste the PAT when prompted
   ```
   (Or, dashboard route: Cloudflare → Workers → Create → paste `worker.js`,
   add a Cron Trigger `*/20 * * * *`, and add an encrypted variable
   `GH_TOKEN`. Optional: add `NOTIFY_WEBHOOK` the same way.)

3. **PROVE the write path** (this is the step the old setup skipped): open
   `https://<worker-url>/?selftest=1` in a browser. It must say
   **`WRITE OK`**. If it says `FAIL 403`, the PAT is still read-only — fix its
   Actions permission and update `GH_TOKEN`, then re-run the self-test.

4. **Optional alerting:** set a `NOTIFY_WEBHOOK` variable to any URL that takes
   a POST `{text}` / `{content}` body — a Discord or Slack channel webhook is
   the zero-cost route. Every dispatch failure then pings you instead of dying
   quietly.

## Notes

- Free tier is ample (72 ticks/day, a few API reads each only near slots).
- `?selftest=1` fires a real (harmless, idempotent) run each time — use it to
  verify, don't hammer it.
- The only required secret is `GH_TOKEN`; rotate it when the PAT nears expiry,
  then re-run the self-test.
- To change slots/formats, edit `SLOTS` in `worker.js` and `wrangler deploy`.
