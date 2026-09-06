from __future__ import annotations

from collections.abc import Mapping

import httpx
from livekit.plugins import openai

from relate_voice.config import LLMConfig


def build_llm(spec: LLMConfig, environment: Mapping[str, str]) -> openai.LLM:
    api_key = environment.get(spec.secret_ref, "")
    return openai.LLM(
        api_key=api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        model=spec.models[0] if spec.models else "gemini-2.0-flash",
        temperature=spec.temperature,
        timeout=httpx.Timeout(spec.timeout_seconds),
    )
