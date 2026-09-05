from __future__ import annotations

from relate_voice.agent import build_session
from relate_voice.config import load_config


def test_session_receives_injected_providers_and_configured_turn_handling(config_path, monkeypatch):
    config = load_config(config_path)
    providers = {"stt": object(), "tts": object(), "llm": object()}
    captured = {}

    class FakeSession:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("relate_voice.agent.AgentSession", FakeSession)

    session = build_session(config, providers)

    assert isinstance(session, FakeSession)
    assert captured["stt"] is providers["stt"]
    assert captured["tts"] is providers["tts"]
    assert captured["llm"] is providers["llm"]
    assert captured["turn_handling"] == {
        "turn_detection": "vad",
        "endpointing": {"min_delay": 0.5, "max_delay": 2.0},
        "interruption": {
            "enabled": True,
            "mode": "vad",
            "min_duration": 0.3,
            "min_words": 0,
            "resume_false_interruption": True,
            "false_interruption_timeout": 1.5,
        },
    }


def test_core_orchestration_has_no_provider_selection_branches():
    source = __import__("inspect").getsource(__import__("relate_voice.agent", fromlist=["build_session"]))

    assert "deepgram" not in source.lower()
    assert "openrouter" not in source.lower()
    assert "poolside/" not in source
