from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from relate_voice.config import VoiceAgentConfig
from relate_voice.providers import deepgram, openrouter

Factory = Callable[[Any, Mapping[str, str]], Any]


class ProviderRegistry:
    def __init__(self) -> None:
        self._factories: dict[tuple[str, str], Factory] = {}

    def register(self, kind: str, name: str, factory: Factory) -> None:
        self._factories[(kind, name)] = factory

    def create(self, kind: str, spec: Any, environment: Mapping[str, str]) -> Any:
        provider = spec.provider
        try:
            factory = self._factories[(kind, provider)]
        except KeyError as exc:
            raise ValueError(f"Unknown {kind} provider: {provider}") from exc
        return factory(spec, environment)

    def create_all(self, config: VoiceAgentConfig, environment: Mapping[str, str]) -> dict[str, Any]:
        return {
            "stt": self.create("stt", config.stt, environment),
            "tts": self.create("tts", config.tts, environment),
            "llm": self.create("llm", config.llm, environment),
        }


def build_default_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register("stt", "deepgram", deepgram.build_stt)
    registry.register("tts", "deepgram", deepgram.build_tts)
    registry.register("llm", "openrouter", openrouter.build_llm)
    return registry
