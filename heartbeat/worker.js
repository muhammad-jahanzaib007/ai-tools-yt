/**
 * Pipeline heartbeat — an EXTERNAL watchdog for the Snackbyte AI (ai-tools-yt)
 * and jahanzaibawan.com (muhammad-jahanzaib007.github.io) GitHub Actions
 * pipelines.
 *
 * Why this exists: GitHub's own cron scheduler has silently skipped scheduled
 * runs for days at a time (2026-07-06..08). Every in-repo backstop
 * (self-heal.yml slot re-dispatch) is ALSO a GitHub cron, so it dies in the
 * exact same outage — GitHub cannot watch itself. This Worker runs on
 * Cloudflare, entirely outside GitHub: on a schedule it checks whether each
 * publish slot actually produced a run, and fires workflow_dispatch if it did
 * not. It is the only backstop that survives a wholesale GitHub scheduler
 * outage.
 *
 * Safety: a workflow_dispatch fired here is NOT skipped by publish.yml's
 * dedupe precheck (that only skips late `schedule` replays). If GitHub later
 * replays the missed cron, THAT replay is skipped because a video already
 * published — so no duplicate. YT slots pass an explicit `format` so a late
 * fire can never flip the format off the wall clock.
 *
 * Secret (set via `wrangler secret put GH_TOKEN` or the dashboard):
 *   GH_TOKEN — a fine-grained PAT with "Actions: Read and write" on BOTH
 *   repos (they share one owner, so one token covers both).
 */

const OWNER = "muhammad-jahanzaib007";

// Slot times are UTC and mirror the crons in each repo. `format` (YT only) is
// forwarded to publish.yml's workflow_dispatch input.
const SLOTS = [
  { repo: "muhammad-jahanzaib007.github.io", wf: "auto-blog.yml", h: 8,  m: 0 },
  { repo: "muhammad-jahanzaib007.github.io", wf: "auto-blog.yml", h: 20, m: 0 },
  { repo: "ai-tools-yt", wf: "publish.yml", h: 11, m: 13, format: "battle" },
  { repo: "ai-tools-yt", wf: "publish.yml", h: 16, m: 13, format: "news" },
  { repo: "ai-tools-yt", wf: "publish.yml", h: 20, m: 13, format: "comic" },
];

// Wait GRACE_MIN after a slot before stepping in (give GitHub's scheduler and
// the in-repo backstops a chance first). Ignore a slot once it is older than
// CUTOFF_MIN — by then a late fire would just be a stale dupe.
const GRACE_MIN = 35;
const CUTOFF_MIN = 165;

async function gh(env, path, init = {}) {
  return fetch(`https://api.github.com${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${env.GH_TOKEN}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "pipeline-heartbeat",
      "X-GitHub-Api-Version": "2022-11-28",
      ...(init.headers || {}),
    },
  });
}

async function checkSlot(env, slot, now) {
  const slotTs = Date.UTC(
    now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), slot.h, slot.m, 0,
  );
  const ageMin = (now.getTime() - slotTs) / 60000;
  const label = `${slot.repo} ${String(slot.h).padStart(2, "0")}:${String(slot.m).padStart(2, "0")}`;
  if (ageMin < GRACE_MIN || ageMin > CUTOFF_MIN) {
    return `${label} — outside window (${ageMin.toFixed(0)}m)`;
  }

  // Was a run of this workflow created at/after the slot time today?
  const r = await gh(env, `/repos/${OWNER}/${slot.repo}/actions/workflows/${slot.wf}/runs?per_page=10`);
  if (!r.ok) return `${label} — run list failed (${r.status})`;
  const data = await r.json();
  const covered = (data.workflow_runs || []).some(
    (run) => Date.parse(run.created_at) >= slotTs,
  );
  if (covered) return `${label} — already covered`;

  // Missed slot -> dispatch it.
  const body = { ref: "main" };
  if (slot.format) body.inputs = { format: slot.format };
  const d = await gh(env,
    `/repos/${OWNER}/${slot.repo}/actions/workflows/${slot.wf}/dispatches`,
    { method: "POST", body: JSON.stringify(body) });
  return `${label} — MISSED, dispatched${slot.format ? ` (${slot.format})` : ""} -> ${d.status}`;
}

async function runAll(env) {
  const now = new Date();
  const results = [];
  for (const slot of SLOTS) {
    try {
      results.push(await checkSlot(env, slot, now));
    } catch (e) {
      results.push(`${slot.repo} ${slot.wf} — error: ${e}`);
    }
  }
  return results;
}

export default {
  // Cloudflare Cron Triggers call this.
  async scheduled(event, env, ctx) {
    ctx.waitUntil(runAll(env).then((r) => console.log(r.join("\n"))));
  },
  // Hit the Worker URL in a browser to run the same check on demand (debug).
  async fetch(request, env) {
    const results = await runAll(env);
    return new Response(results.join("\n") + "\n", {
      headers: { "content-type": "text/plain" },
    });
  },
};
