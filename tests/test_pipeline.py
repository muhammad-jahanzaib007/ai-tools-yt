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
