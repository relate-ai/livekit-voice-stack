from __future__ import annotations

import asyncio
import logging
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
    TurnHandlingOptions,
)

from relate_voice.config import VoiceAgentConfig
from relate_voice.providers.registry import ProviderRegistry, build_default_registry

logger = logging.getLogger("relate_voice.agent")


class VoiceAgent(Agent):
    def __init__(self, config: VoiceAgentConfig) -> None:
        super().__init__(instructions=config.agent.instructions)


def build_session(config: VoiceAgentConfig, providers: Mapping[str, Any]) -> AgentSession[Any]:
    interruption = config.turn_handling.interruption
    endpointing = config.turn_handling.endpointing
    return AgentSession(
        stt=providers["stt"],
        llm=providers["llm"],
        tts=providers["tts"],
        turn_handling=TurnHandlingOptions(
            turn_detection=config.turn_handling.turn_detection,
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
        ),
    )


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


async def voice_session(ctx: agents.JobContext) -> None:
    if _ACTIVE_CONFIG is None or _ACTIVE_REGISTRY is None:
        raise RuntimeError("Voice worker is not initialised")
    providers = _ACTIVE_REGISTRY.create_all(_ACTIVE_CONFIG, _ACTIVE_ENVIRONMENT)
    session = build_session(_ACTIVE_CONFIG, providers)

    async def report_model(model: str, provider: str) -> None:
        try:
            await ctx.room.local_participant.set_attributes(
                {"relate_active_llm_model": model, "relate_active_llm_provider": provider}
            )
        except Exception as exc:
            logger.warning("model attribution failed: %s", type(exc).__name__)

    _register_safe_observability(session, _ACTIVE_CONFIG, report_model)
    await session.start(room=ctx.room, agent=VoiceAgent(_ACTIVE_CONFIG))
    await session.generate_reply(instructions=_ACTIVE_CONFIG.agent.greeting)


def build_server(
    config: VoiceAgentConfig,
    environment: Mapping[str, str],
    registry: ProviderRegistry | None = None,
) -> AgentServer:
    global _ACTIVE_CONFIG, _ACTIVE_ENVIRONMENT, _ACTIVE_REGISTRY
    _ACTIVE_CONFIG = config
    _ACTIVE_ENVIRONMENT = dict(environment)
    _ACTIVE_REGISTRY = registry or build_default_registry()
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
