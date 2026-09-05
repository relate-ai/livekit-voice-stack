from __future__ import annotations

from collections.abc import Mapping

from livekit.plugins import deepgram

from relate_voice.config import STTConfig, TTSConfig


def build_stt(spec: STTConfig, environment: Mapping[str, str]) -> deepgram.STT:
    return deepgram.STT(
        api_key=environment[spec.secret_ref],
        base_url=str(spec.endpoint),
        model=spec.model,
        language=spec.language,
        smart_format=spec.smart_format,
        endpointing_ms=spec.endpointing_ms,
        mip_opt_out=spec.mip_opt_out,
    )


def build_tts(spec: TTSConfig, environment: Mapping[str, str]) -> deepgram.TTS:
    provider_model = f"{spec.model}-{spec.voice}-{spec.language}"
    return deepgram.TTS(
        api_key=environment[spec.secret_ref],
        base_url=str(spec.endpoint),
        model=provider_model,
        sample_rate=spec.sample_rate,
        mip_opt_out=spec.mip_opt_out,
    )
