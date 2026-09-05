from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from relate_voice.config import (
    AUTHORISED_OPENROUTER_MODELS,
    load_config,
    validate_secret_references,
)


def test_loads_all_independent_configuration_sections(config_path):
    config = load_config(config_path)

    assert config.stt.provider == "deepgram"
    assert config.tts.provider == "deepgram"
    assert config.tts.voice == "asteria"
    assert config.llm.models == list(AUTHORISED_OPENROUTER_MODELS)
    assert config.turn_handling.interruption.enabled is True
    assert config.ui.public_url == "https://voice.relate-ai.site"


def test_unknown_configuration_fields_are_rejected(config_path):
    config = load_config(config_path)
    raw = config.model_dump()
    raw["llm"]["paid_backup"] = "openai/gpt-5"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        type(config).model_validate(raw)


@pytest.mark.parametrize(
    "models",
    [
        ["z-ai/glm-5.2:free", "poolside/laguna-xs-2.1:free", "cohere/north-mini-code:free"],
        ["poolside/laguna-xs-2.1:free", "openai/gpt-5", "cohere/north-mini-code:free"],
        ["poolside/laguna-xs-2.1:free"],
    ],
)
def test_llm_chain_must_match_exact_authorised_order(config_path, models):
    raw = deepcopy(load_config(config_path).model_dump())
    raw["llm"]["models"] = models

    with pytest.raises(ValidationError, match="exact authorised free model chain"):
        type(load_config(config_path)).model_validate(raw)


def test_missing_secret_reference_fails_before_worker_accepts_jobs(config_path, secret_environment):
    config = load_config(config_path)
    secret_environment.pop("OPENROUTER_API_KEY")

    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        validate_secret_references(config, secret_environment)
