from __future__ import annotations

from livekit.agents import JobExecutorType
from livekit.agents.inference import TurnDetector

from relate_voice.agent import build_server, build_session, voice_session
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
    assert isinstance(captured["turn_handling"]["turn_detection"], TurnDetector)
    assert captured["turn_handling"]["endpointing"] == {"min_delay": 0.5, "max_delay": 3.0}
    assert captured["turn_handling"]["interruption"] == {
        "enabled": True,
        "mode": "vad",
        "min_duration": 0.5,
        "min_words": 0,
        "resume_false_interruption": True,
        "false_interruption_timeout": 2.0,
    }
    assert captured["turn_handling"]["preemptive_generation"] == {
        "enabled": True,
        "preemptive_tts": False,
        "max_speech_duration": 10.0,
        "max_retries": 3,
    }


def test_worker_uses_thread_executor_and_top_level_entrypoint(config_path):
    config = load_config(config_path)
    environment = {
        "LIVEKIT_URL": "ws://localhost:7880",
        "LIVEKIT_API_KEY": "key",
        "LIVEKIT_API_SECRET": "secret",
    }

    server = build_server(config, environment)

    assert server._job_executor_type is JobExecutorType.THREAD
    assert voice_session.__module__ == "relate_voice.agent"
    assert "<locals>" not in voice_session.__qualname__


def test_first_llm_model_is_reported_once_for_attribution():
    import asyncio

    from relate_voice.agent import _register_safe_observability

    handlers = {}

    class FakeSession:
        def on(self, event):
            def wrap(func):
                handlers[event] = func
                return func

            return wrap

    reported = []

    async def on_model(model, provider):
        reported.append((model, provider))

    class Metadata:
        model_name = "cohere/north-mini-code:free"
        model_provider = "openrouter"

    class Metrics:
        type = "llm_metrics"
        metadata = Metadata()

    class STTMetadata:
        model_name = "nova-3"
        model_provider = "deepgram"

    class STTMetrics:
        type = "stt_metrics"
        metadata = STTMetadata()

    class Event:
        metrics = Metrics()

    class FakeConfig:
        observability = type("Obs", (), {"log_model_identity": True})()

    _register_safe_observability(FakeSession(), FakeConfig(), on_model)

    class STTEvent:
        metrics = STTMetrics()

    async def drive():
        handlers["metrics_collected"](STTEvent())
        handlers["metrics_collected"](Event())
        handlers["metrics_collected"](Event())
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    asyncio.run(drive())

    assert reported == [("cohere/north-mini-code:free", "openrouter")]


def test_core_orchestration_has_no_provider_selection_branches():
    source = __import__("inspect").getsource(__import__("relate_voice.agent", fromlist=["build_session"]))

    assert "deepgram" not in source.lower()
    assert "openrouter" not in source.lower()
    assert "poolside/" not in source
