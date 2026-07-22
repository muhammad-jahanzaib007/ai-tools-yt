"""Tests for the pure functions the pipeline has actually been burned by:
JSON extraction (2026-07-05 outage), LLM-output validation, take scoring,
style-leak detection, and news ranking helpers. No network, no audio."""

import sys
import datetime as dt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "automation"))

import generate_brief as gb
import render_video as rv
import news_sources as ns
import audio_qa as aq
import ig_analytics as iga
import screen_capture as sc
import capture_batch as cbatch
import crosspost as cp


# --- chat_json extraction (the 2026-07-05 outage class) -----------------------

def test_extract_plain_json():
    assert gb._extract_first_json_block('{"a": 1}') == '{"a": 1}'


def test_extract_fenced_json():
    assert gb._extract_first_json_block('```json\n{"a": 1}\n```') == '{"a": 1}'


def test_extract_prose_wrapped_nested():
    got = gb._extract_first_json_block('sure! {"a": {"b": 2}} hope that helps')
    assert got == '{"a": {"b": 2}}'


def test_extract_truncated_returns_none():
    assert gb._extract_first_json_block('{"a": {"b": 2}') is None


def test_extract_no_json_returns_none():
    assert gb._extract_first_json_block("no json here") is None


def test_strip_em_dash():
    assert gb.strip_em("fast — really fast") == "fast, really fast"
    assert gb.strip_em("mid—word") == "mid-word"


# --- battle block validation ---------------------------------------------------

def _battle(rounds=2, winner="a"):
    return {
        "toolA": "ChatGPT", "toolB": "Writesonic", "tagline": "Who writes better?",
        "verdict": "ChatGPT wins overall; Writesonic is still better for ads.",
        "rounds": [{"title": f"R{i}", "aPoint": "fast", "bPoint": "cheap",
                    "winner": winner} for i in range(rounds)],
    }


def _narration(n):
    return [{"text": f"seg {i}", "broll": "laptop"} for i in range(n)]


def test_clean_battle_valid():
    out = gb._clean_battle(_battle(rounds=2), _narration(4))
    assert out and out["toolA"] == "ChatGPT" and len(out["rounds"]) == 2


def test_clean_battle_bad_winner_dropped():
    assert gb._clean_battle(_battle(winner="c"), _narration(4)) is None


def test_clean_battle_wrong_narration_count_dropped():
    assert gb._clean_battle(_battle(rounds=2), _narration(5)) is None


def test_clean_battle_too_few_rounds_dropped():
    assert gb._clean_battle(_battle(rounds=1), _narration(3)) is None


def test_clean_battle_keeps_declared_champion():
    bt = _battle(rounds=2)
    bt["champion"] = "B"                       # case-insensitive
    out = gb._clean_battle(bt, _narration(4))
    assert out["champion"] == "b"


def test_champion_derived_from_majority():
    bt = _battle(rounds=3, winner="b")
    out = gb._clean_battle(bt, _narration(5))
    assert out["champion"] == "b"


def test_champion_split_uses_verdict_first_name():
    # 1-1 split; the verdict opens with the winner's name (toolA here).
    bt = _battle(rounds=2)
    bt["rounds"][1]["winner"] = "b"
    out = gb._clean_battle(bt, _narration(4))
    assert out["champion"] == "a"              # "ChatGPT wins overall; ..."
    bt["verdict"] = "Writesonic wins overall; ChatGPT still better for code."
    out = gb._clean_battle(bt, _narration(4))
    assert out["champion"] == "b"


def test_champion_split_no_name_defaults_a():
    bt = _battle(rounds=2)
    bt["rounds"][1]["winner"] = "b"
    bt["verdict"] = "Both are great, honestly a coin flip for most people."
    out = gb._clean_battle(bt, _narration(4))
    assert out["champion"] == "a"


# --- ranking block validation ----------------------------------------------------

def _ranking(n=5, ranks=None):
    ranks = ranks if ranks is not None else list(range(n, 0, -1))
    return {
        "theme": "Free AI tools that beat paid ones",
        "cta": "Disagree with number one? Comment.",
        "items": [{"rank": r, "name": f"Tool{r}", "reason": "does the job free",
                   "tag": "Free"} for r in ranks],
    }


def test_clean_ranking_valid():
    out = gb._clean_ranking(_ranking(), _narration(7))
    assert out and len(out["items"]) == 5 and out["items"][0]["rank"] == 5
    assert out["items"][-1]["rank"] == 1


def test_clean_ranking_wrong_count_dropped():
    assert gb._clean_ranking(_ranking(n=4), _narration(6)) is None


def test_clean_ranking_wrong_order_dropped():
    assert gb._clean_ranking(_ranking(ranks=[1, 2, 3, 4, 5]), _narration(7)) is None


def test_clean_ranking_wrong_narration_count_dropped():
    assert gb._clean_ranking(_ranking(), _narration(6)) is None


def test_clean_ranking_empty_field_dropped():
    rk = _ranking()
    rk["items"][2]["reason"] = ""
    assert gb._clean_ranking(rk, _narration(7)) is None


# --- news block validation (hard grounding gate) --------------------------------

def _news(n_stories=3, category="chips"):
    return {
        "headline": "AI moves fast", "outro": "Follow for tomorrow's brief.",
        "stories": [{"title": f"Story {i}", "source": "TechCrunch",
                     "category": category, "detail": "A concrete line."}
                    for i in range(n_stories)],
    }


def test_clean_news_valid():
    out = gb._clean_news(_news(3), _narration(5))
    assert out and len(out["stories"]) == 3


def test_clean_news_unknown_category_defaults_to_apps():
    out = gb._clean_news(_news(3, category="bananas"), _narration(5))
    assert out and all(s["category"] == "apps" for s in out["stories"])


def test_clean_news_wrong_narration_count_dropped():
    assert gb._clean_news(_news(3), _narration(4)) is None


def test_clean_news_empty_field_dropped():
    bad = _news(3)
    bad["stories"][0]["detail"] = ""
    assert gb._clean_news(bad, _narration(5)) is None


# --- voice take QA helpers -------------------------------------------------------

def test_norm_words():
    assert rv._norm_words("It's FAST, really!") == ["it's", "fast", "really"]


def test_style_leaked_detects_spoken_prompt():
    style = "Say the following like an urgent, confident news anchor:"
    text = "Markets rose sharply today after the announcement."
    hyp = "urgent confident news anchor markets rose sharply today after the announcement"
    assert rv._style_leaked(style, text, hyp) is True


def test_style_leaked_clean_take_passes():
    style = "Say the following like an urgent, confident news anchor:"
    text = "Markets rose sharply today after the announcement."
    assert rv._style_leaked(style, text, text.lower()) is False


def test_take_score_leak_heavily_penalised():
    assert rv._take_score(3.0, 0.0, leaked=True) < rv._take_score(1.0, 0.3, leaked=False)


def test_take_score_intelligibility_dominates_pitch():
    assert rv._take_score(1.0, 0.05) > rv._take_score(6.0, 0.5)


def test_take_score_rushed_take_loses_to_in_pace_peer():
    # Same clarity and liveliness: the in-pace take must win.
    assert rv._take_score(3.0, 0.1, pace=3.4) < rv._take_score(3.0, 0.1, pace=2.8)


def test_take_score_rush_penalty_never_beats_intelligibility():
    # A rushed-but-clear take still outranks a garbled slow one.
    assert rv._take_score(3.0, 0.05, pace=3.6) > rv._take_score(3.0, 0.5, pace=2.8)


def test_pace_from_word_timings():
    words = [("w%d" % i, i * 0.25, i * 0.25 + 0.25) for i in range(16)]
    text = " ".join(w for w, *_ in words)     # 16 words over 4.0s = 4.0 wps
    assert abs(rv._pace(text, words) - 4.0) < 1e-6


def test_pace_short_segment_not_judged():
    words = [("hi", 0.0, 0.2), ("there", 0.2, 0.4)]
    assert rv._pace("hi there", words) is None
    assert rv._pace("some words here", []) is None


# --- news source helpers ----------------------------------------------------------

def test_tokens_drop_stopwords_and_short():
    assert ns._tokens("The AI is on a new GPU") == {"gpu"}


def test_category_chips():
    item = {"title": "Nvidia unveils next-gen GPU for data center compute",
            "summary": ""}
    assert ns._category(item) == "chips"


def test_parse_date_rfc822_and_iso():
    assert ns._parse_date("Mon, 06 Jul 2026 09:00:00 GMT").year == 2026
    d = ns._parse_date("2026-07-06T09:00:00Z")
    assert d is not None and d.tzinfo is not None


def test_parse_date_garbage_none():
    assert ns._parse_date("not a date") is None


def test_align_script_to_timings_fixes_brand_mishears():
    # Whisper mishears "ChatGPT" as "Chachi Pt"; captions must use the script.
    script = "Is ChatGPT better than Claude for coding"
    whisper = [("Is", 0.0, 0.2), ("Chachi", 0.2, 0.5), ("Pt", 0.5, 0.8),
               ("better", 0.8, 1.1), ("than", 1.1, 1.3), ("Claude", 1.3, 1.7),
               ("for", 1.7, 1.9), ("coding", 1.9, 2.3)]
    out = rv._align_script_to_timings(script, whisper)
    assert [w for w, _, _ in out] == script.split()
    assert all(s <= e for _, s, e in out)                 # each word well-formed
    assert [s for _, s, _ in out] == sorted(s for _, s, _ in out)  # non-decreasing


def test_align_drops_hallucinations_and_restores_missed_words():
    script = "Synthesia makes avatars"
    whisper = [("Synthesia", 0.0, 0.4), ("um", 0.4, 0.5), ("makes", 0.5, 0.8)]
    out = rv._align_script_to_timings(script, whisper)
    assert [w for w, _, _ in out] == ["Synthesia", "makes", "avatars"]


def test_align_empty_falls_back():
    assert rv._align_script_to_timings("", [("x", 0.0, 0.1)]) == [("x", 0.0, 0.1)]
    assert rv._align_script_to_timings("hi", []) == []


def test_margin_at_picks_window():
    margins = [(5.0, 10.0, 830), (12.0, 20.0, 830)]
    assert rv._margin_at(0.0, margins) == 0       # intro: style default
    assert rv._margin_at(5.0, margins) == 830     # window start inclusive
    assert rv._margin_at(9.9, margins) == 830
    assert rv._margin_at(10.0, margins) == 0      # window end exclusive
    assert rv._margin_at(15.0, margins) == 830
    assert rv._margin_at(25.0, margins) == 0
    assert rv._margin_at(3.0, None) == 0


def test_scene_cuts_exclude_next_word_onset():
    # Two scenes, 0.6s pause between them. The old midpoint cut put the
    # front 0.3s of the pause (breath + next-word pre-voicing) in scene 0.
    scenes = [[("hello", 0.0, 0.5), ("world", 0.6, 1.0)],
              [("next", 1.6, 2.0), ("scene", 2.1, 2.5)]]
    pts = _scene_cut_points_helper(scenes, 3.0)
    (s0, e0), (s1, e1) = pts
    assert s0 == 0.0
    assert e0 == 1.0 + 0.12          # short tail only, not (1.0+1.6)/2
    assert s1 == 1.6 - 0.10          # short lead keeps the word's own onset
    assert e0 < s1                   # clips never overlap
    assert e1 == 3.0                 # last scene keeps trailing audio


def test_scene_cuts_tiny_gap_no_overlap():
    # 0.1s gap: tail/lead shrink to 30% of the gap each.
    scenes = [[("a", 0.0, 1.0)], [("b", 1.1, 2.0)]]
    (s0, e0), (s1, e1) = _scene_cut_points_helper(scenes, 2.4)
    assert abs(e0 - 1.03) < 1e-9
    assert abs(s1 - 1.07) < 1e-9
    assert e0 <= s1


def test_scene_cuts_negative_gap_clamps():
    # Whisper drift can overlap word timings across the boundary.
    scenes = [[("a", 0.0, 1.2)], [("b", 1.1, 2.0)]]
    (s0, e0), (s1, e1) = _scene_cut_points_helper(scenes, 2.4)
    assert e0 == 1.2                 # no tail into the next word
    assert s1 == 1.1                 # no lead into the previous word
    assert e1 == 2.4


def test_scene_cuts_min_clip_length():
    scenes = [[("a", 0.0, 0.05)], [("b", 5.0, 5.5)]]
    (s0, e0), _ = _scene_cut_points_helper(scenes, 6.0)
    assert e0 - s0 >= 0.20


def _scene_cut_points_helper(scenes, full_dur):
    return rv._scene_cut_points(scenes, full_dur)


def test_karaoke_ass_lifts_captions_in_windows(tmp_path):
    words = [("intro", 0.0, 0.5), ("word", 0.6, 1.0),
             ("rank", 6.0, 6.4), ("scene", 6.5, 7.0)]
    out = tmp_path / "subs.ass"
    rv.build_karaoke_ass(words, out, group=2, margins=[(5.0, 10.0, 830)])
    lines = [l for l in out.read_text(encoding="utf-8").splitlines()
             if l.startswith("Dialogue:")]
    assert ",0,0,0,," in lines[0]      # intro chunk keeps style margin
    assert ",0,0,830,," in lines[1]    # rank-scene chunk lifted above block


# --- audio QA take ordering (2026-07-22 wer=0.51 false-GARBLED incident) ------

def test_sorted_takes_numeric_not_lexicographic():
    # A 13-segment b-roll-fallback narration produces a0..a12.mp3. String sort
    # puts 'a10'/'a11'/'a12' before 'a2'..'a9', scrambling the transcript order
    # that script_wer() compares word-for-word against the sequential script.
    names = [f"a{i}.mp3" for i in (0, 1, 10, 11, 12, 2, 3, 4, 5, 6, 7, 8, 9)]
    paths = [Path(n) for n in names]
    out = [p.name for p in aq._sorted_takes(paths)]
    assert out == [f"a{i}.mp3" for i in range(13)]


def test_sorted_takes_single_digit_unaffected():
    paths = [Path(f"a{i}.mp3") for i in (2, 0, 1, 4, 3)]
    out = [p.name for p in aq._sorted_takes(paths)]
    assert out == ["a0.mp3", "a1.mp3", "a2.mp3", "a3.mp3", "a4.mp3"]


# --- IG insights metric-rejection parsing (2026-07-22 stale-retry incident) ---

def test_drop_rejected_metric_allowed_values_form():
    # Meta's actual 2026-07-22 error shape: no per-metric phrase, just an
    # allowed-values list. The old phrase-matching check never fired on this.
    metrics = ["reach", "views", "ig_reels_avg_watch_time",
               "ig_reels_video_view_total_count", "saved", "shares",
               "likes", "comments"]
    body = ('{"error":{"message":"(#100) metric[3] must be one of the '
            'following values: impressions, reach, replies, saved, likes, '
            'comments, shares, total_interactions"}}')
    out = iga._drop_rejected_metric(metrics, body)
    assert out == ["reach", "saved", "shares", "likes", "comments"]


def test_drop_rejected_metric_named_phrase_form():
    metrics = ["reach", "plays", "saved"]
    body = '{"error":{"message":"plays does not support this operation"}}'
    assert iga._drop_rejected_metric(metrics, body) == ["reach", "saved"]


def test_drop_rejected_metric_no_match_returns_none():
    assert iga._drop_rejected_metric(["reach"], "totally unrelated 500 error") is None


# --- screen-capture demo crop geometry -----------------------------------------

def test_crop_filter_centers_and_targets_916():
    vf = sc._crop_filter(720, 1180)
    # target width = 1180 * 9/16 = 663.75 -> 663; x offset centers it in 720
    assert vf == "crop=663:1180:28:0,scale=1080:1920"


# --- capture-batch prompt selection (local-PC library builder) ----------------

def test_pick_prompts_avoids_used_prompts():
    manifest = {"clips": [{"prompt": cbatch.PROMPT_POOL[0]},
                          {"prompt": cbatch.PROMPT_POOL[1]}]}
    picked = cbatch.pick_prompts(manifest, len(cbatch.PROMPT_POOL) - 2)
    assert cbatch.PROMPT_POOL[0] not in picked
    assert cbatch.PROMPT_POOL[1] not in picked


def test_pick_prompts_falls_back_to_repeats_when_pool_exhausted():
    manifest = {"clips": [{"prompt": p} for p in cbatch.PROMPT_POOL]}
    picked = cbatch.pick_prompts(manifest, 2)
    assert len(picked) == 2
    assert all(p in cbatch.PROMPT_POOL for p in picked)


def test_pick_prompts_respects_count():
    assert len(cbatch.pick_prompts({"clips": []}, 3)) == 3


def test_fetch_pexels_photo_no_key_returns_false(monkeypatch, tmp_path):
    monkeypatch.setattr(cbatch, "PX_KEY", None)
    assert cbatch.fetch_pexels_photo("dog", tmp_path / "out.jpg") is False


# --- TikTok manual-upload queue (2026-07-22: API rejected, stage-only now) ----

def test_tiktok_queue_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(cp, "TIKTOK_QUEUE", tmp_path / "tiktok_manual_queue.json")
    q = cp.load_tiktok_queue()
    assert q == {"pending": []}
    q["pending"].append({"slug": "demo-vs-thing", "url": "https://example.com/demo.mp4"})
    cp.save_tiktok_queue(q)
    reloaded = cp.load_tiktok_queue()
    assert reloaded["pending"][0]["slug"] == "demo-vs-thing"


def test_tiktok_no_longer_auto_posts():
    # post_tiktok/_tiktok_access_token were removed with the API path (2026-07-22
    # rejection) - guard against either silently reappearing.
    assert not hasattr(cp, "post_tiktok")
    assert not hasattr(cp, "_tiktok_access_token")
