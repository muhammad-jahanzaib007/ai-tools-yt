/**
 * Pipeline heartbeat — the SINGLE SCHEDULER for the Snackbyte AI (ai-tools-yt)
 * and jahanzaibawan.com (muhammad-jahanzaib007.github.io) GitHub Actions
 * pipelines.
 *
 * PROMOTED FROM BACKSTOP TO SOLE FIRING SOURCE (2026-07-11): GitHub's cron
 * scheduler fires late, replays runs hours later, and skips whole days
 * (2026-07-06..08). Running GitHub crons AND this Worker meant two firing
 * sources racing each other — that race double-published 3 slots in 36 h
 * (2026-07-10/11) even with dedupe patches. Both repos now have NO
 * `schedule:` crons at all; this Worker is the only thing that fires
 * publish/blog slots:
 *   - Cron triggers at the EXACT slot minutes dispatch immediately.
 *   - :20/:40 sweep ticks retry any slot still uncovered (failed dispatch,
 *     Cloudflare hiccup) — but only once the slot is MIN_RETRY_MIN old, so a
 *     just-dispatched run that hasn't appeared in the runs list yet can
 *     never be double-fired.
 *   - Coverage is checked against GitHub's runs API before every dispatch,
 *     so any tick is idempotent: a covered slot is never fired again.
 * If this Worker dies entirely, nothing publishes — by design (one source).
 * The alarm for that is watchdog.yml (GitHub cron, checks upload freshness
 * daily) plus the receipts going stale.
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

// Slot times are UTC. These are THE schedule now (the repos have no crons);
// wrangler.toml's slot-minute cron triggers MUST match these times.
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

// There is no grace period any more — this Worker IS the scheduler, so the
// slot-minute tick dispatches at age ~0. Retry sweeps (:20/:40 ticks) only
// act on a slot at least MIN_RETRY_MIN old: a dispatch's run row can lag a
// little in GitHub's runs API, and firing again inside that lag would be
// the one remaining duplicate path. Ignore a slot older than CUTOFF_MIN —
// by then a fire would just be a stale surprise (and with the 2-format map,
// no age inside CUTOFF_MIN crosses the 15:00 format boundary).
const MIN_RETRY_MIN = 10;
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

async function checkSlot(env, slot, now, act) {
  const slotTs = Date.UTC(
    now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), slot.h, slot.m, 0,
  );
  const ageMin = (now.getTime() - slotTs) / 60000;
  // Show the pinned format in every status line so a stale dashboard paste
  // (SLOTS out of sync with publish.yml) is visible from the / endpoint.
  const label = `${slot.repo} ${String(slot.h).padStart(2, "0")}:${String(slot.m).padStart(2, "0")}` +
    (slot.format ? ` [${slot.format}]` : "");
  if (ageMin < 0 || ageMin > CUTOFF_MIN) {
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

  // Read-only callers (the / status page) must never mutate anything: a
  // human peeking at the dashboard should not be what fires a slot
  // (2026-07-11: a status curl beat the cron tick to a cover dispatch).
  if (!act) return `${label} — UNCOVERED (a cron tick will dispatch it)`;

  // The slot-minute tick dispatches at age ~0; a retry sweep must wait out
  // the runs-API lag window so it can't double-fire a fresh dispatch.
  if (ageMin >= 1.5 && ageMin < MIN_RETRY_MIN) {
    return `${label} — dispatched recently, awaiting run row (${ageMin.toFixed(0)}m)`;
  }

  // Uncovered slot -> dispatch it, and VERIFY the dispatch succeeded.
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

async function runAll(env, act) {
  const now = new Date();
  const results = [];
  for (const slot of SLOTS) {
    try {
      results.push(await checkSlot(env, slot, now, act));
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
    ctx.waitUntil(runAll(env, true).then((r) => console.log(r.join("\n"))));
  },
  // Hit the Worker URL in a browser:
  //   /              -> per-slot coverage + token health (READ-ONLY: never
  //                     dispatches; only the cron tick covers missed slots)
  //   /?selftest=1   -> actively prove the write path (dispatches token-check)
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.searchParams.get("selftest") === "1") {
      const out = await selfTest(env);
      return new Response(out + "\n", { headers: { "content-type": "text/plain" } });
    }
    const results = await runAll(env, false);
    const health = await tokenHealth(env);
    return new Response(results.join("\n") + "\n\n" + health + "\n", {
      headers: { "content-type": "text/plain" },
    });
  },
};
