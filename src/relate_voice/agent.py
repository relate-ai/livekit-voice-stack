from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Callable, Coroutine, Mapping
from typing import Any

from livekit import agents
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    EndpointingOptions,
    InterruptionOptions,
    JobExecutorType,
    PreemptiveGenerationOptions,
    TurnHandlingOptions,
    UserTurnLimitOptions,
)
from livekit.agents import inference

from relate_voice.agent_store import AgentStore, AgentPackage
from relate_voice.config import VoiceAgentConfig
from relate_voice.providers.registry import ProviderRegistry, build_default_registry

logger = logging.getLogger("relate_voice.agent")


def _resolve_config_from_agent(
    pkg: AgentPackage, base_config: VoiceAgentConfig
) -> VoiceAgentConfig:
    """Build a VoiceAgentConfig from an AgentPackage, falling back to base_config for missing refs."""
    from relate_voice.agent_store import LLMProviderConfig
    data = base_config.model_dump()
    # Override LLM
    data["llm"]["provider"] = pkg.llm.provider
    data["llm"]["models"] = [pkg.llm.model]
    data["llm"]["temperature"] = pkg.llm.temperature
    data["llm"]["max_tokens"] = pkg.llm.max_tokens
    data["llm"]["timeout_seconds"] = pkg.llm.timeout_seconds
    # Override agent instructions/greeting
    data["agent"]["instructions"] = pkg.personality
    data["agent"]["greeting"] = pkg.greeting
    # Override speech
    data["stt"]["provider"] = pkg.speech.stt_provider
    data["stt"]["model"] = pkg.speech.stt_model
    data["stt"]["language"] = pkg.speech.stt_language
    data["tts"]["provider"] = pkg.speech.tts_provider
    data["tts"]["model"] = pkg.speech.tts_model
    data["tts"]["voice"] = pkg.speech.tts_voice
    data["tts"]["language"] = pkg.speech.tts_language
    # Override turn handling
    data["turn_handling"]["turn_detection"] = pkg.turn_handling.turn_detection
    data["turn_handling"]["endpointing"]["min_delay_seconds"] = pkg.turn_handling.endpointing_min_delay
    data["turn_handling"]["endpointing"]["max_delay_seconds"] = pkg.turn_handling.endpointing_max_delay
    data["turn_handling"]["interruption"]["enabled"] = pkg.turn_handling.interruption_enabled
    data["turn_handling"]["interruption"]["mode"] = pkg.turn_handling.interruption_mode
    data["turn_handling"]["interruption"]["min_duration_seconds"] = pkg.turn_handling.interruption_min_duration
    data["turn_handling"]["preemptive_generation"]["enabled"] = pkg.turn_handling.preemptive_generation
    data["turn_handling"]["user_turn_limit"]["max_words"] = pkg.turn_handling.user_turn_max_words
    data["turn_handling"]["user_turn_limit"]["max_duration"] = pkg.turn_handling.user_turn_max_duration
    return VoiceAgentConfig.model_validate(data)


class VoiceAgent(Agent):
    def __init__(self, config: VoiceAgentConfig) -> None:
        super().__init__(instructions=config.agent.instructions)


def build_session(config: VoiceAgentConfig, providers: Mapping[str, Any]) -> AgentSession[Any]:
    interruption = config.turn_handling.interruption
    endpointing = config.turn_handling.endpointing
    preemptive = config.turn_handling.preemptive_generation
    turn_limit = config.turn_handling.user_turn_limit

    if config.turn_handling.turn_detection == "turn_detector":
        turn_detection: Any = inference.TurnDetector()
    else:
        turn_detection = config.turn_handling.turn_detection

    session_kwargs: dict[str, Any] = dict(
        stt=providers["stt"],
        llm=providers["llm"],
        tts=providers["tts"],
        turn_handling=TurnHandlingOptions(
            turn_detection=turn_detection,
            endpointing=EndpointingOptions(
                min_delay=endpointing.min_delay_seconds,
                max_delay=endpointing.max_delay_seconds,
            ),
            interruption=InterruptionOptions(
                enabled=interruption.enabled,
                mode=interruption.mode,
                min_duration=interruption.min_duration_seconds,
                min_words=interruption.min_words,
                resume_false_interruption=interruption.resume_false_interruption,
                false_interruption_timeout=interruption.false_interruption_timeout_seconds,
            ),
            preemptive_generation=PreemptiveGenerationOptions(
                enabled=preemptive.enabled,
                preemptive_tts=preemptive.preemptive_tts,
                max_speech_duration=preemptive.max_speech_duration,
                max_retries=preemptive.max_retries,
            ),
        ),
    )

    if turn_limit.max_words is not None or turn_limit.max_duration is not None:
        session_kwargs["turn_handling"]["user_turn_limit"] = UserTurnLimitOptions(
            max_words=turn_limit.max_words,
            max_duration=turn_limit.max_duration,
        )

    return AgentSession(**session_kwargs)


def _register_safe_observability(
    session: AgentSession[Any],
    config: VoiceAgentConfig,
    on_model: Callable[[str, str], Coroutine[Any, Any, None]] | None = None,
) -> None:
    reported = False

    @session.on("agent_state_changed")
    def agent_state_changed(event: Any) -> None:
        logger.info("agent_state state=%s", event.new_state)

    @session.on("user_state_changed")
    def user_state_changed(event: Any) -> None:
        logger.info("user_state state=%s", event.new_state)

    @session.on("metrics_collected")
    def metrics_collected(event: Any) -> None:
        nonlocal reported
        metrics = event.metrics
        if getattr(metrics, "type", None) != "llm_metrics":
            return
        metadata = getattr(metrics, "metadata", None)
        model = (
            getattr(metadata, "model_name", None)
            or getattr(metrics, "model_name", None)
            or getattr(metrics, "model", None)
        )
        provider = (
            getattr(metadata, "model_provider", None) or getattr(metrics, "provider", None)
        )
        if config.observability.log_model_identity:
            logger.info(
                "provider_metrics type=%s provider=%s model=%s",
                type(metrics).__name__,
                provider or "unknown",
                model or "unknown",
            )
        if on_model is not None and not reported and model:
            reported = True
            try:
                asyncio.get_running_loop().create_task(on_model(model, provider or "unknown"))
            except RuntimeError:
                pass

    @session.on("error")
    def session_error(event: Any) -> None:
        error = getattr(event, "error", None)
        logger.error("session_error type=%s", type(error).__name__ if error else "unknown")


_ACTIVE_CONFIG: VoiceAgentConfig | None = None
_ACTIVE_ENVIRONMENT: dict[str, str] = {}
_ACTIVE_REGISTRY: ProviderRegistry | None = None
_AGENT_STORE: AgentStore | None = None


async def voice_session(ctx: agents.JobContext) -> None:
    if _ACTIVE_CONFIG is None or _ACTIVE_REGISTRY is None:
        raise RuntimeError("Voice worker is not initialised")

    # Check for active agent in store
    config = _ACTIVE_CONFIG
    if _AGENT_STORE is not None:
        active = _AGENT_STORE.get_active_agent()
        if active:
            logger.info("Using active agent: %s v%s (llm=%s/%s)", active.agent_id, active.version, active.llm.provider, active.llm.model)
            config = _resolve_config_from_agent(active, _ACTIVE_CONFIG)

    providers = _ACTIVE_REGISTRY.create_all(config, _ACTIVE_ENVIRONMENT)
    session = build_session(config, providers)

    async def report_model(model: str, provider: str) -> None:
        try:
            attrs = {"relate_active_llm_model": model, "relate_active_llm_provider": provider}
            if _AGENT_STORE is not None:
                active = _AGENT_STORE.get_active_agent()
                if active:
                    attrs["relate_agent_id"] = active.agent_id
                    attrs["relate_agent_version"] = active.version
            await ctx.room.local_participant.set_attributes(attrs)
        except Exception as exc:
            logger.warning("model attribution failed: %s", type(exc).__name__)

    _register_safe_observability(session, config, report_model)
    await session.start(room=ctx.room, agent=VoiceAgent(config))
    await session.generate_reply(instructions=config.agent.greeting)


def build_server(
    config: VoiceAgentConfig,
    environment: Mapping[str, str],
    registry: ProviderRegistry | None = None,
) -> AgentServer:
    global _ACTIVE_CONFIG, _ACTIVE_ENVIRONMENT, _ACTIVE_REGISTRY, _AGENT_STORE
    _ACTIVE_CONFIG = config
    _ACTIVE_ENVIRONMENT = dict(environment)
    _ACTIVE_REGISTRY = registry or build_default_registry()
    _AGENT_STORE = AgentStore(os.environ.get("AGENT_STORE_PATH", "/data/agents"))
    server = AgentServer(
        ws_url=_ACTIVE_ENVIRONMENT["LIVEKIT_URL"],
        api_key=_ACTIVE_ENVIRONMENT["LIVEKIT_API_KEY"],
        api_secret=_ACTIVE_ENVIRONMENT["LIVEKIT_API_SECRET"],
        drain_timeout=300,
        job_executor_type=JobExecutorType.THREAD,
        num_idle_processes=1,
        prometheus_port=config.observability.prometheus_port,
        log_level=config.observability.log_level,
    )
    server.rtc_session(agent_name=config.agent.dispatch_name)(voice_session)
    return server
