from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]


def _compose() -> dict:
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text())


def test_only_authorised_livekit_media_ports_are_published():
    compose = _compose()
    published = [port for service in compose["services"].values() for port in service.get("ports", [])]

    assert published == ["7881:7881/tcp", "7882:7882/udp"]


def test_turn_is_explicitly_disabled():
    config = _compose()["configs"]["livekit"]["content"]

    assert "turn:\n  enabled: false" in config


def test_private_services_are_not_routed_or_published():
    compose = _compose()

    for name in ("redis", "agent"):
        assert "ports" not in compose["services"][name]
        environment = compose["services"][name].get("environment", {})
        assert not any(key.startswith("SERVICE_FQDN") for key in environment)


def test_secrets_are_scoped_to_only_the_services_that_use_them():
    compose = _compose()
    agent_env = compose["services"]["agent"]["environment"]
    web_env = compose["services"]["web"]["environment"]

    assert "WEB_SESSION_SECRET" not in agent_env
    assert "DEEPGRAM_API_KEY" not in web_env
    assert "OPENROUTER_API_KEY" not in web_env


def test_images_and_dependencies_are_pinned():
    compose_text = (ROOT / "docker-compose.yml").read_text()
    requirements = (ROOT / "pyproject.toml").read_text()

    livekit_image = (
        "livekit/livekit-server@sha256:e37d68f172556d02aa77968b9fc55ef481468c0315fa38e4fa6c56ce72e3a815"
    )
    redis_image = "redis@sha256:0302cccee2b2043e61b497c8f4075467c5f7ba27a9f38be7e092634f2734baed"
    assert livekit_image in compose_text
    assert redis_image in compose_text
    assert "livekit-agents==1.8.0" in requirements


def test_all_services_have_health_or_dependency_gates_and_log_caps():
    compose = _compose()

    for service in compose["services"].values():
        assert "healthcheck" in service
        assert service["logging"]["options"] == {"max-file": "3", "max-size": "10m"}


def test_runtime_secrets_are_not_required_during_coolify_build_interpolation():
    compose_text = (ROOT / "docker-compose.yml").read_text()

    assert ":?}" not in compose_text


def test_livekit_proxy_port_is_exposed_and_keys_are_configured():
    compose = _compose()
    livekit = compose["services"]["livekit"]
    config = compose["configs"]["livekit"]["content"]

    assert "7880" in livekit.get("expose", [])
    assert "keys:" in config
    assert "LIVEKIT_API_KEY" in config
    assert "LIVEKIT_API_SECRET" in config
