from __future__ import annotations

import pytest

from relate_voice.config import load_config
from relate_voice.providers.base import ProviderError, ProviderErrorCategory
from relate_voice.providers.registry import ProviderRegistry, build_default_registry


def test_mock_provider_extends_registry_without_orchestration_changes(config_path, secret_environment):
    config = load_config(config_path)
    registry = ProviderRegistry()
    registry.register("stt", "mock", lambda spec, env: {"kind": "mock-stt", "model": spec.model})

    mock_spec = config.stt.model_copy(update={"provider": "mock"})

    assert registry.create("stt", mock_spec, secret_environment) == {
        "kind": "mock-stt",
        "model": "nova-3",
    }


def test_unknown_provider_is_rejected(config_path, secret_environment):
    config = load_config(config_path)

    with pytest.raises(ValueError, match="Unknown stt provider"):
        ProviderRegistry().create("stt", config.stt, secret_environment)


def test_default_registry_builds_all_configured_provider_roles(config_path, secret_environment, monkeypatch):
    config = load_config(config_path)
    registry = build_default_registry()
    created: list[tuple[str, str]] = []

    for kind, provider in (("stt", "deepgram"), ("tts", "deepgram"), ("llm", "openrouter")):

        def factory(spec, env, kind=kind):
            created.append((kind, spec.provider))
            return kind

        registry.register(kind, provider, factory)

    providers = registry.create_all(config, secret_environment)

    assert providers == {"stt": "stt", "tts": "tts", "llm": "llm"}
    assert created == [("stt", "deepgram"), ("tts", "deepgram"), ("llm", "openrouter")]


@pytest.mark.parametrize(
    ("category", "eligible"),
    [
        (ProviderErrorCategory.RATE_LIMIT, True),
        (ProviderErrorCategory.TIMEOUT, True),
        (ProviderErrorCategory.TRANSIENT, True),
        (ProviderErrorCategory.UNAVAILABLE, True),
        (ProviderErrorCategory.AUTHENTICATION, False),
        (ProviderErrorCategory.INVALID_REQUEST, False),
        (ProviderErrorCategory.CONFIGURATION, False),
        (ProviderErrorCategory.APPLICATION, False),
    ],
)
def test_fallback_eligibility_is_semantically_bounded(category, eligible):
    error = ProviderError(category, "redacted upstream failure")

    assert error.fallback_eligible is eligible
