from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from livekit import agents
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    EndpointingOptions,
    InterruptionOptions,
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


def _register_safe_observability(session: AgentSession[Any], config: VoiceAgentConfig) -> None:
    @session.on("agent_state_changed")
    def agent_state_changed(event: Any) -> None:
        logger.info("agent_state state=%s", event.new_state)

    @session.on("user_state_changed")
    def user_state_changed(event: Any) -> None:
        logger.info("user_state state=%s", event.new_state)

    @session.on("metrics_collected")
    def metrics_collected(event: Any) -> None:
        metrics = event.metrics
        model = getattr(metrics, "model_name", None) or getattr(metrics, "model", None)
        provider = getattr(metrics, "provider", None)
        if config.observability.log_model_identity:
            logger.info(
                "provider_metrics type=%s provider=%s model=%s",
                type(metrics).__name__,
                provider or "unknown",
                model or "unknown",
            )

    @session.on("error")
    def session_error(event: Any) -> None:
        error = getattr(event, "error", None)
        logger.error("session_error type=%s", type(error).__name__ if error else "unknown")


def build_server(
    config: VoiceAgentConfig,
    environment: Mapping[str, str],
    registry: ProviderRegistry | None = None,
) -> AgentServer:
    registry = registry or build_default_registry()
    server = AgentServer(
        ws_url=environment["LIVEKIT_URL"],
        api_key=environment["LIVEKIT_API_KEY"],
        api_secret=environment["LIVEKIT_API_SECRET"],
        drain_timeout=300,
        num_idle_processes=1,
        prometheus_port=config.observability.prometheus_port,
        log_level=config.observability.log_level,
    )

    @server.rtc_session(agent_name=config.agent.dispatch_name)
    async def voice_session(ctx: agents.JobContext) -> None:
        providers = registry.create_all(config, environment)
        session = build_session(config, providers)
        _register_safe_observability(session, config)
        await session.start(room=ctx.room, agent=VoiceAgent(config))
        await session.generate_reply(instructions=config.agent.greeting)

    return server
