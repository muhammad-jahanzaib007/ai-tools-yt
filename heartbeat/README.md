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
   `GH_TOKEN`.)

3. **Verify:** open the Worker's URL in a browser — it runs the same check on
   demand and prints one line per slot (`outside window` / `already covered` /
   `MISSED, dispatched`).

## Notes

- Free tier is ample (72 ticks/day, a few API reads each only near slots).
- The only secret is `GH_TOKEN`; rotate it when the PAT nears expiry.
- To change slots/formats, edit `SLOTS` in `worker.js` and `wrangler deploy`.
