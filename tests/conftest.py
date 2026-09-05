from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def config_path() -> Path:
    return Path(__file__).parents[1] / "config" / "voice-agent.yaml"


@pytest.fixture
def secret_environment() -> dict[str, str]:
    return {
        "DEEPGRAM_API_KEY": "test-deepgram-key",
        "OPENROUTER_API_KEY": "test-openrouter-key",
        "LIVEKIT_API_KEY": "test-livekit-key",
        "LIVEKIT_API_SECRET": "test-livekit-secret-at-least-thirty-two-bytes",
        "WEB_SESSION_SECRET": "test-web-session-secret-long-enough",
    }
