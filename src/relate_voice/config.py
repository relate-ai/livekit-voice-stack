from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

AUTHORISED_OPENROUTER_MODELS = (
    "poolside/laguna-xs-2.1:free",
    "z-ai/glm-5.2:free",
    "cohere/north-mini-code:free",
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class STTConfig(StrictModel):
    provider: str
    model: str
    language: str
    endpoint: HttpUrl
    secret_ref: str
    smart_format: bool = True
    endpointing_ms: int = Field(default=300, ge=10, le=5000)
    mip_opt_out: bool = True


class TTSConfig(StrictModel):
    provider: str
    model: str
    voice: str
    language: str
    endpoint: HttpUrl
    secret_ref: str
    sample_rate: int = Field(default=24000, ge=8000, le=48000)
    mip_opt_out: bool = True


class LLMConfig(StrictModel):
    provider: str
    endpoint: HttpUrl
    secret_ref: str
    models: list[str]
    site_url: HttpUrl
    app_name: str
    temperature: float = Field(default=0.4, ge=0, le=2)
    max_tokens: int = Field(default=300, ge=32, le=2000)
    timeout_seconds: float = Field(default=20, gt=0, le=60)

    @field_validator("models")
    @classmethod
    def validate_models(cls, models: list[str]) -> list[str]:
        if tuple(models) != AUTHORISED_OPENROUTER_MODELS:
            raise ValueError("models must equal the exact authorised free model chain")
        return models


class FallbackConfig(StrictModel):
    eligible_http_statuses: list[int]
    eligible_categories: list[str]
    max_attempts_per_model: int = Field(default=1, ge=1, le=3)


class EndpointingConfig(StrictModel):
    min_delay_seconds: float = Field(default=0.5, ge=0.1, le=3)
    max_delay_seconds: float = Field(default=3.0, ge=0.2, le=5)


class InterruptionConfig(StrictModel):
    enabled: bool = True
    mode: Literal["adaptive", "vad"] = "vad"
    min_duration_seconds: float = Field(default=0.5, ge=0.05, le=2)
    min_words: int = Field(default=0, ge=0, le=10)
    resume_false_interruption: bool = True
    false_interruption_timeout_seconds: float = Field(default=2.0, ge=0.1, le=5)


class PreemptiveGenerationConfig(StrictModel):
    enabled: bool = True
    preemptive_tts: bool = False
    max_speech_duration: float = Field(default=10.0, gt=0, le=30)
    max_retries: int = Field(default=3, ge=1, le=5)


class UserTurnLimitConfig(StrictModel):
    max_words: int | None = Field(default=None, ge=10, le=500)
    max_duration: float | None = Field(default=None, ge=5, le=120)


class TurnHandlingConfig(StrictModel):
    turn_detection: Literal["stt", "vad", "realtime_llm", "manual", "turn_detector"] = "turn_detector"
    endpointing: EndpointingConfig = EndpointingConfig()
    interruption: InterruptionConfig = InterruptionConfig()
    preemptive_generation: PreemptiveGenerationConfig = PreemptiveGenerationConfig()
    user_turn_limit: UserTurnLimitConfig = UserTurnLimitConfig()


class AgentConfig(StrictModel):
    dispatch_name: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9-]+$")
    display_name: str = Field(min_length=1, max_length=80)
    instructions: str = Field(min_length=1, max_length=4000)
    greeting: str = Field(min_length=1, max_length=500)


class UIConfig(StrictModel):
    public_url: str = Field(pattern=r"^https://")
    livekit_url: str = Field(pattern=r"^wss://")
    token_ttl_seconds: int = Field(default=120, ge=30, le=300)
    max_sessions_per_window: int = Field(default=10, ge=1, le=100)
    rate_window_seconds: int = Field(default=3600, ge=60, le=86400)


class ObservabilityConfig(StrictModel):
    log_level: str
    log_model_identity: bool
    log_prompts: bool = False
    prometheus_port: int = Field(default=9090, ge=1024, le=65535)


class VoiceAgentConfig(StrictModel):
    stt: STTConfig
    tts: TTSConfig
    llm: LLMConfig
    fallback: FallbackConfig
    turn_handling: TurnHandlingConfig
    agent: AgentConfig
    ui: UIConfig
    observability: ObservabilityConfig


def load_config(path: str | Path) -> VoiceAgentConfig:
    with Path(path).open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    return VoiceAgentConfig.model_validate(raw)


def validate_secret_references(config: VoiceAgentConfig, environment: Mapping[str, str]) -> None:
    required = {
        config.stt.secret_ref,
        config.tts.secret_ref,
        config.llm.secret_ref,
        "LIVEKIT_API_KEY",
        "LIVEKIT_API_SECRET",
        "WEB_SESSION_SECRET",
    }
    missing = sorted(name for name in required if not environment.get(name))
    if missing:
        raise RuntimeError(f"Missing required secret references: {', '.join(missing)}")


def validate_agent_secret_references(config: VoiceAgentConfig, environment: Mapping[str, str]) -> None:
    required = {
        config.stt.secret_ref,
        config.tts.secret_ref,
        config.llm.secret_ref,
        "LIVEKIT_API_KEY",
        "LIVEKIT_API_SECRET",
    }
    missing = sorted(name for name in required if not environment.get(name))
    if missing:
        raise RuntimeError(f"Missing required agent secret references: {', '.join(missing)}")


def validate_web_secret_references(environment: Mapping[str, str]) -> None:
    required = {"LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", "WEB_SESSION_SECRET"}
    missing = sorted(name for name in required if not environment.get(name))
    if missing:
        raise RuntimeError(f"Missing required web secret references: {', '.join(missing)}")
