# Faceless AI-tools YouTube automation

Fully-automated faceless YouTube channel about AI tools and AI news.
Runs free on GitHub Actions (public repo = unlimited minutes). The only paid
piece is ElevenLabs (~$5/mo) for natural narration, added in Phase 2.

## Status
- **Phase 1 — content engine (DONE):** `automation/generate_brief.py` turns a
  topic into a structured video brief (title, hook, narration segments with
  per-segment b-roll search terms, description, tags, thumbnail text) using
  **GitHub Models** for free. Output lands in `briefs/<slug>.json`.
- **Phase 2 — render (next):** ElevenLabs voice -> Pexels b-roll -> burned
  captions -> music -> `ffmpeg` MP4, uploaded as an Actions artifact to review.
- **Phase 3 — auto-upload:** YouTube Data API uploads on a cron, hands-off.

## One-time setup
1. This repo must be **public** (free Actions minutes).
2. **Settings -> Actions -> General -> Workflow permissions -> Read and write.**
3. Ensure **GitHub Models** is enabled for your account (free): github.com/settings/models
4. Phase 2 secrets (add later): `ELEVENLABS_API_KEY`, `PEXELS_API_KEY`.
5. Phase 3: a Google Cloud project with YouTube Data API + OAuth refresh token.

## Test Phase 1 now
Actions tab -> **Generate video brief (Phase 1)** -> Run workflow.
Check the committed `briefs/*.json` (and the run artifact) for quality.

## The brief contract (what Phase 2 consumes)
```json
{
  "slug": "...", "title": "...", "hook": "...",
  "narration": [ { "text": "spoken line", "broll": "stock search query" } ],
  "description": "... Tools mentioned and links: [AFFILIATE_LINKS]",
  "tags": ["..."], "thumbnail_text": "...", "topic": "...", "date": "YYYY-MM-DD"
}
```
