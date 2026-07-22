#!/usr/bin/env python3
"""Screen-capture demos: record a real AI tool actually doing a task, for the
"same task, visible output" Short format (the 59M-view "Apple AI vs Samsung
AI" pattern) — the untried lever after the 2026-07-22 checkpoint verdict
killed the text-card battle/ranking formats (median avg watch time 3.2s on
40-60s videos; see performance-turnaround memory).

Each TASK_LIBRARY entry describes one free, no-login web tool and exactly how
to drive it: fill a prompt, click generate, wait for a real output element to
appear. capture() drives it with Playwright, recording the whole interaction
as a portrait-ish video via BrowserContext(record_video_dir=...) — no manual
screen-recording software, and the resulting clip is real footage, not a
staged screenshot.

CORRECTED 2026-07-22 (do not trust the first "it worked" without re-testing
from a cold vanilla Playwright launch): the interactive Playwright MCP tool
got a real generated image from perchance.org/ai-text-to-image-generator,
but a plain `playwright.chromium.launch()` — the same call this module
actually uses in production — does NOT reliably work against it, in EITHER
headless or headed mode, from EITHER a GitHub Actions cloud IP or the
owner's residential IP:
  - Cloudflare's "Performing security verification" Turnstile page appears
    on a cold launch (confirmed via a debug screenshot, both cloud and
    residential) — inconsistently; a later headed/residential run got past
    it to the real page.
  - Even past that wall, the actual image never rendered: the console
    showed `image-generation.perchance.org` itself returning 403 with
    `X-Frame-Options: sameorigin`, so the embed iframe that's supposed to
    hold the generated <img> never loads at all.
The MCP tool's earlier success most likely came from something a vanilla
launch doesn't have — an already-trusted session/cookies from prior manual
navigation, a stealth-patched or real "chrome" channel browser, or both —
none of which is something to actively engineer around here: Cloudflare's
wall + the server's own 403 are the site telling us not to script it, and
defeating that on purpose is a different, uglier decision than "the
selector was wrong." TASK_LIBRARY is kept as a real, working example of the
calling shape, but perchance-image should NOT be trusted as production-ready
until proven otherwise from a cold session.

THIRD CANDIDATE WORKED (2026-07-22): Pixian.ai hit a second, different block
(a disguised "Network Error" — its WebSocket "worker" connection never
completes; `navigator.webdriver` reads True by default in vanilla Playwright,
a common, trivial bot tell many sites soft-block on without ever showing an
explicit CAPTCHA). imgupscaler.ai, tried third, has none of this: a real
upload completed in ~7s from a cold headless launch on the first two tries,
no wall of any kind. Two tools blocked in a row didn't mean the whole
approach was dead — it meant those two specific tools were bot-hardened.
Keep testing candidates cold before trusting one, but don't over-generalize
a block into "this lever is impossible" either.

QUOTA CAVEAT, same session: its free tier is a shared per-IP/device credit
pool (started at 8, visible on-page) — repeated manual testing during this
build drained it to 2, and the 3rd/4th attempts then stalled well past the
normal ~7s (quota pressure, not a new bot-wall — confirmed by watching
credits count down 8→6→4→2 across successive runs). Same mistake class as
the 2026-07-17 Gemini-TTS smoke-test quota drain: don't hit a real,
rate-limited free tool repeatedly from CI/tests. Any smoke test for this
task must NOT call the live site (mock/skip it), exactly like
smoke-render.yml switched to VOICE_PROVIDER=edge for that reason.

CLI: python screen_capture.py <task_name> "<prompt-or-file-path>" <out.mp4>
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / ".render"

# Portrait-ish viewport so the recording needs minimal cropping for a 9:16
# Short (see crop_to_vertical). Wider than true 9:16 because most of these
# tools' desktop layouts don't reflow narrow enough to hide surrounding UI.
CAPTURE_VIEWPORT = {"width": 720, "height": 1180}

TASK_LIBRARY = {
    # NOT confirmed production-ready — see the module docstring's 2026-07-22
    # correction. The selector shape below (control iframe holds the prompt
    # box/button; the real <img> lands in separate dynamically-created
    # image-generation.perchance.org/embed iframes as base64 data) is
    # correct and DOM-verified, but a cold `chromium.launch()` gets blocked
    # before ever reaching that <img> often enough that this isn't usable
    # unattended yet.
    "perchance-image": {
        "mode": "prompt",
        "url": "https://perchance.org/ai-text-to-image-generator",
        "iframe": "#outputIframeEl",
        "prompt_role": ("textbox", None),   # (role, accessible-name substring; None = first match)
        "submit_role": ("button", "generate"),
        "wait_strategy": "perchance_embed_image",
        "timeout_s": 60,
        "settle_s": 1.0,        # let the reveal animation/paint finish before recording ends
    },
    # CONFIRMED WORKING 2026-07-22 from a cold headless `chromium.launch()`
    # (the third candidate tried, after perchance and Pixian.ai both hit bot
    # walls — see the module docstring). No login, no CAPTCHA, no soft-block:
    # a real upload completes in ~7s and the site swaps in a second "Original"
    # tab once done. `input_value` for this task is a local image path to
    # upload, not a text prompt.
    "imgupscaler-upscale": {
        "mode": "upload",
        "url": "https://imgupscaler.ai",
        "file_input": "input[type=file]",
        "wait_strategy": "imgupscaler_original_label",
        "timeout_s": 40,
        "settle_s": 1.5,
    },
}


def _resolve_target(frame, role, name):
    loc = frame.get_by_role(role, name=name) if name else frame.get_by_role(role)
    return loc.first


def _wait_perchance_embed_image(page, timeout_s):
    """Poll page.frames for the dynamically-created image-generation.perchance
    .org/embed iframe(s) and block until the first one's <img> has actually
    finished loading (naturalWidth>0 and complete) — a plain frame_locator
    wait_for doesn't work here since these frames don't exist at page-load
    and there can be several (one per generated image)."""
    end = time.time() + timeout_s
    while time.time() < end:
        embeds = [f for f in page.frames
                  if f.url.startswith("https://image-generation.perchance.org/embed")]
        for f in embeds:
            try:
                info = f.locator("img").first.evaluate(
                    "el => ({w: el.naturalWidth, complete: el.complete})")
            except Exception:
                continue
            if info.get("complete") and info.get("w", 0) > 0:
                return
        time.sleep(0.5)
    raise RuntimeError("timed out waiting for a generated image")


def _wait_imgupscaler_done(page, timeout_s):
    """Block until imgupscaler.ai's second ("Original") result tab appears —
    it's only added to the DOM once processing actually finishes, so it's a
    clean completion signal without guessing at a spinner disappearing."""
    page.get_by_text("Original", exact=True).first.wait_for(
        state="visible", timeout=timeout_s * 1000)


WAIT_STRATEGIES = {
    "perchance_embed_image": _wait_perchance_embed_image,
    "imgupscaler_original_label": _wait_imgupscaler_done,
}


def capture(task_name, input_value, out_path, headless=True):
    """Record one live run of `task_name`, writing an mp4 to `out_path`.
    `input_value` is a text prompt for mode="prompt" tasks, or a local image
    file path for mode="upload" tasks. Raises on any step failure — callers
    should treat a failed capture like a failed pexels_clip() call (drop to
    a fallback, don't block the whole render)."""
    from playwright.sync_api import sync_playwright

    task = TASK_LIBRARY[task_name]
    out_path = Path(out_path)
    video_dir = WORK / f"capture_{task_name}_{int(time.time())}"
    video_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            viewport=CAPTURE_VIEWPORT,
            record_video_dir=str(video_dir),
            record_video_size=CAPTURE_VIEWPORT,
        )
        page = context.new_page()
        try:
            page.goto(task["url"], wait_until="domcontentloaded", timeout=30_000)
            # domcontentloaded fires before a hydration-heavy SPA finishes
            # wiring up its JS event handlers - set_input_files only waits
            # for the element to be attached, not for the site's own onChange
            # listener to be live. Without this pause the file lands in the
            # <input> but nothing happens (confirmed 2026-07-22: manual tests
            # that had an incidental pause here worked; production capture()
            # without one silently stalled on a cold page every time, cloud
            # AND residential, credits unused - not a wall, not quota).
            page.wait_for_timeout(2000)

            if task.get("mode") == "upload":
                page.locator(task["file_input"]).first.set_input_files(str(input_value))
            else:
                frame = page.frame_locator(task["iframe"]) if task.get("iframe") else page
                role, name = task["prompt_role"]
                _resolve_target(frame, role, name).fill(input_value)
                role, name = task["submit_role"]
                _resolve_target(frame, role, name).click()

            WAIT_STRATEGIES[task["wait_strategy"]](page, task["timeout_s"])
            page.wait_for_timeout(int(task["settle_s"] * 1000))
        except Exception:
            # Debug evidence for "why did this fail" (bot-wall vs a plain
            # timing/headless quirk) instead of guessing from a bare
            # TimeoutError - a screenshot answers it in one look.
            debug_shot = Path(out_path).with_suffix(".debug.png")
            try:
                page.screenshot(path=str(debug_shot))
                print(f"debug screenshot saved: {debug_shot}", file=sys.stderr)
            except Exception as shot_err:
                print(f"debug screenshot also failed: {shot_err}", file=sys.stderr)
            context.close()
            browser.close()
            raise

        video_path = page.video.path()
        context.close()      # finalizes the .webm; must happen before reading video_path's bytes
        browser.close()

    _to_portrait_mp4(Path(video_path), out_path)
    for f in video_dir.glob("*"):
        f.unlink(missing_ok=True)
    video_dir.rmdir()
    return out_path


def _crop_filter(w, h):
    """9:16 center-crop ffmpeg -vf string for a `w`x`h` source. Pure so the
    geometry is unit-testable without ffmpeg or a real recording."""
    target_w = int(h * 9 / 16)          # crop width for a true 9:16 frame at height h
    x_off = max(0, (w - target_w) // 2)
    return f"crop={target_w}:{h}:{x_off}:0,scale=1080:1920"


def _to_portrait_mp4(webm_path, out_path):
    """Crop the recorded viewport to true 9:16 and transcode to mp4 (Remotion
    b-roll expects mp4, and .webm's vp8/vp9 isn't the h264 the rest of the
    pipeline mixes)."""
    import subprocess
    vf = _crop_filter(CAPTURE_VIEWPORT["width"], CAPTURE_VIEWPORT["height"])
    p = subprocess.run(
        ["ffmpeg", "-y", "-i", str(webm_path), "-vf", vf,
         "-c:v", "libx264", "-preset", "veryfast", "-an", str(out_path)],
        capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"capture transcode failed: {p.stderr[-500:]}")


def main():
    if len(sys.argv) != 4:
        sys.exit("usage: screen_capture.py <task_name> <prompt> <out.mp4>")
    task_name, prompt, out = sys.argv[1], sys.argv[2], sys.argv[3]
    if task_name not in TASK_LIBRARY:
        sys.exit(f"unknown task {task_name!r}; options: {', '.join(TASK_LIBRARY)}")
    path = capture(task_name, prompt, out)
    print(f"captured: {path}")


if __name__ == "__main__":
    main()
