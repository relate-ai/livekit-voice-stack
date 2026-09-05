from __future__ import annotations

import math
import struct

from relate_voice.harness import api_base, find_speech_end, frame_rms, fuzzy_contains, speech_active


def test_api_base_maps_ws_schemes_to_http():
    assert api_base("ws://livekit:7880") == "http://livekit:7880"
    assert api_base("wss://livekit.relate-ai.site") == "https://livekit.relate-ai.site"


def test_fuzzy_contains_matches_case_and_punctuation_variants():
    assert fuzzy_contains("Hello! How can I HELP you today?", "help")
    assert fuzzy_contains("The code word is blueberry.", "BLUEBERRY")
    assert fuzzy_contains("Four. Anything else?", "four")


def test_fuzzy_contains_rejects_absent_content():
    assert not fuzzy_contains("Hello, how can I help?", "blueberry")
    assert not fuzzy_contains("", "help")


def test_frame_rms_distinguishes_silence_from_tone():
    silence = b"\x00" * 960
    tone = struct.pack("<48h", *[int(8000 * math.sin(i / 4)) for i in range(48)])

    assert frame_rms(silence) == 0.0
    assert frame_rms(tone) > 1000.0


def test_speech_active_uses_threshold():
    assert speech_active(0.0, threshold=500.0) is False
    assert speech_active(1200.0, threshold=500.0) is True


def test_find_speech_end_requires_sustained_silence():
    active = [True] * 50 + [False] * 10 + [True] * 5 + [False] * 100

    assert find_speech_end(active, start=0, min_silence=40) == 65 + 40


def test_find_speech_end_returns_none_without_enough_silence():
    active = [True] * 50 + [False] * 10

    assert find_speech_end(active, start=0, min_silence=40) is None
