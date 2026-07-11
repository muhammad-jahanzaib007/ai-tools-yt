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
 * TRUST MODEL (2026-07-10 rebuild): the previous version failed SILENTLY for
 * days — its dispatch POST returned 403 (the PAT lacked "Actions: write") and
 * nobody noticed, because only the READ path (listing runs) was ever
 * exercised and a failed dispatch was not surfaced. This version fixes that:
 *   1. A dispatch that does NOT return HTTP 204 is treated as a FAILURE:
 *      logged loudly and (if NOTIFY_WEBHOOK is set) pushed to the owner.
 *   2. `GET /?selftest=1` on the Worker URL actively PROVES the write path by
 *      dispatching a harmless idempotent workflow (YT token-check.yml) and
 *      reporting the raw status — 204 = write works, 403 = PAT still read-only,
 *      404 = token can't see the repo. Run this after any token change.
 *   3. `GET /` reports each slot's coverage AND a read-path token health line.
 *
 * Secrets (Cloudflare → Worker → Settings → Variables, or `wrangler secret put`):
 *   GH_TOKEN        fine-grained PAT, "Actions: Read and write" on BOTH repos
 *                   (same owner, one token covers both). REQUIRED.
 *   NOTIFY_WEBHOOK  optional. Any URL that accepts a POST JSON body
 *                   {text: "..."} — a Discord/Slack webhook, or an email-relay.
 *                   If set, dispatch failures and run-list failures ping it.
 */

const OWNER = "muhammad-jahanzaib007";

// Slot times are UTC and mirror the crons in each repo.
const SLOTS = [
  { repo: "muhammad-jahanzaib007.github.io", wf: "auto-blog.yml", h: 8,  m: 0 },
  { repo: "muhammad-jahanzaib007.github.io", wf: "auto-blog.yml", h: 20, m: 0 },
  // NO format field: publish.yml's "Pick format by slot" derives the format
  // from the clock for dispatches, and with the 2-format map (hour<15 battle,
  // else ranking) no cover window inside CUTOFF_MIN crosses a format
  // boundary. Formats live in ONE place (publish.yml) — a stale dashboard
  // paste of this file can no longer ship the wrong format (2026-07-11: a
  // drifted paste dispatched a ranking into the 10:59 battle slot).
  { repo: "ai-tools-yt", wf: "publish.yml", h: 10, m: 59 },
  { repo: "ai-tools-yt", wf: "publish.yml", h: 15, m: 59 },
  { repo: "ai-tools-yt", wf: "publish.yml", h: 19, m: 59 },
];

// Wait GRACE_MIN after a slot before stepping in (give GitHub's scheduler and
// the in-repo backstops a chance first). Ignore a slot once it is older than
// CUTOFF_MIN — by then a late fire would just be a stale dupe.
// GRACE must exceed publish.yml precheck's 90-min replay-skip threshold:
// 2026-07-11 a cron replay 50 min late collided with a 41-min heartbeat
// cover (the 35..90-min window where both can fire) and shipped a
// duplicate. At 100 min: a <=90-min-late cron always runs alone, and any
// later replay of a heartbeat-covered slot is skipped by precheck.
const GRACE_MIN = 100;
const CUTOFF_MIN = 165;

// Harmless, idempotent workflow used to prove the token's write path.
const SELFTEST = { repo: "ai-tools-yt", wf: "token-check.yml" };

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

async function notify(env, text) {
  if (!env.NOTIFY_WEBHOOK) return;
  try {
    await fetch(env.NOTIFY_WEBHOOK, {
      method: "POST",
      headers: { "content-type": "application/json" },
      // {content} for Discord, {text} for Slack/most relays — send both.
      body: JSON.stringify({ text, content: text }),
    });
  } catch (e) {
    console.log(`notify failed: ${e}`);
  }
}

async function dispatch(env, repo, wf, inputs) {
  const body = { ref: "main" };
  if (inputs) body.inputs = inputs;
  const r = await gh(env,
    `/repos/${OWNER}/${repo}/actions/workflows/${wf}/dispatches`,
    { method: "POST", body: JSON.stringify(body) });
  // A successful workflow_dispatch returns 204 No Content. Anything else is a
  // failure whose status is the diagnosis: 403 = PAT lacks Actions:write,
  // 404 = token can't see the repo/workflow, 422 = bad ref/inputs.
  return r.status;
}

async function checkSlot(env, slot, now) {
  const slotTs = Date.UTC(
    now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), slot.h, slot.m, 0,
  );
  const ageMin = (now.getTime() - slotTs) / 60000;
  // Show the pinned format in every status line so a stale dashboard paste
  // (SLOTS out of sync with publish.yml) is visible from the / endpoint.
  const label = `${slot.repo} ${String(slot.h).padStart(2, "0")}:${String(slot.m).padStart(2, "0")}` +
    (slot.format ? ` [${slot.format}]` : "");
  if (ageMin < GRACE_MIN || ageMin > CUTOFF_MIN) {
    return `${label} — outside window (${ageMin.toFixed(0)}m)`;
  }

  // Was a run of this workflow created at/after the slot time today?
  const r = await gh(env, `/repos/${OWNER}/${slot.repo}/actions/workflows/${slot.wf}/runs?per_page=10`);
  if (!r.ok) {
    const msg = `${label} — run list failed (${r.status})`;
    await notify(env, `heartbeat: ${msg}`);
    return msg;
  }
  const data = await r.json();
  const covered = (data.workflow_runs || []).some(
    (run) => Date.parse(run.created_at) >= slotTs,
  );
  if (covered) return `${label} — already covered`;

  // Missed slot -> dispatch it, and VERIFY the dispatch succeeded.
  const status = await dispatch(env, slot.repo, slot.wf, slot.format ? { format: slot.format } : null);
  const fmt = slot.format ? ` (${slot.format})` : "";
  if (status === 204) {
    return `${label} — MISSED, dispatched${fmt} OK`;
  }
  const msg = `${label} — MISSED, DISPATCH FAILED status=${status}${fmt}` +
    (status === 403 ? " (PAT lacks Actions:write)" : status === 404 ? " (token can't see repo)" : "");
  await notify(env, `heartbeat: ${msg}`);
  return msg;
}

async function runAll(env) {
  const now = new Date();
  const results = [];
  for (const slot of SLOTS) {
    try {
      results.push(await checkSlot(env, slot, now));
    } catch (e) {
      const msg = `${slot.repo} ${slot.wf} — error: ${e}`;
      await notify(env, `heartbeat: ${msg}`);
      results.push(msg);
    }
  }
  return results;
}

// Actively prove the write path: dispatch the harmless token-check workflow and
// report the raw status. This is the ONE thing the old version never did.
async function selfTest(env) {
  const status = await dispatch(env, SELFTEST.repo, SELFTEST.wf, null);
  const verdict = status === 204
    ? "WRITE OK — the PAT can dispatch workflows. Heartbeat will work."
    : status === 403
      ? "FAIL 403 — the PAT still lacks 'Actions: Read and write'. Re-mint it."
      : status === 404
        ? "FAIL 404 — the PAT cannot see this repo. Fix repository access."
        : `FAIL ${status} — unexpected; check the token.`;
  return `selftest: dispatched ${SELFTEST.repo}/${SELFTEST.wf} -> HTTP ${status}\n${verdict}`;
}

// Read-path token health: confirm the token authenticates at all.
async function tokenHealth(env) {
  const r = await gh(env, `/repos/${OWNER}/ai-tools-yt`);
  if (r.status === 200) return "token: read OK (authenticates, sees ai-tools-yt)";
  if (r.status === 401) return "token: 401 — invalid or expired GH_TOKEN";
  return `token: read returned ${r.status}`;
}

export default {
  // Cloudflare Cron Triggers call this.
  async scheduled(event, env, ctx) {
    ctx.waitUntil(runAll(env).then((r) => console.log(r.join("\n"))));
  },
  // Hit the Worker URL in a browser:
  //   /              -> per-slot coverage + read-path token health
  //   /?selftest=1   -> actively prove the write path (dispatches token-check)
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.searchParams.get("selftest") === "1") {
      const out = await selfTest(env);
      return new Response(out + "\n", { headers: { "content-type": "text/plain" } });
    }
    const results = await runAll(env);
    const health = await tokenHealth(env);
    return new Response(results.join("\n") + "\n\n" + health + "\n", {
      headers: { "content-type": "text/plain" },
    });
  },
};
