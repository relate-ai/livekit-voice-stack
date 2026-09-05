from __future__ import annotations

import base64
import json

from fastapi.testclient import TestClient

from relate_voice.config import load_config
from relate_voice.web import create_app


def _jwt_payload(token: str) -> dict:
    encoded = token.split(".")[1]
    encoded += "=" * (-len(encoded) % 4)
    return json.loads(base64.urlsafe_b64decode(encoded))


def test_session_endpoint_requires_same_origin_browser_session(config_path, secret_environment):
    client = TestClient(create_app(load_config(config_path), secret_environment))

    response = client.post("/api/session", headers={"Origin": "https://attacker.example"})

    assert response.status_code == 403
    assert "token" not in response.text.lower()


def test_session_endpoint_mints_short_lived_room_scoped_token(config_path, secret_environment):
    config = load_config(config_path)
    client = TestClient(create_app(config, secret_environment), base_url=config.ui.public_url)
    page = client.get("/")

    response = client.post("/api/session", headers={"Origin": config.ui.public_url})

    assert page.status_code == 200
    assert response.status_code == 201
    body = response.json()
    claims = _jwt_payload(body["token"])
    assert body["server_url"] == "wss://livekit.relate-ai.site"
    assert claims["video"] == {
        "canPublish": True,
        "canPublishData": False,
        "canPublishSources": ["microphone"],
        "canSubscribe": True,
        "room": body["room_name"],
        "roomJoin": True,
    }
    assert claims["exp"] - claims["nbf"] <= config.ui.token_ttl_seconds + 1
    assert claims["roomConfig"]["agents"][0]["agentName"] == config.agent.dispatch_name


def test_security_headers_are_present(config_path, secret_environment):
    client = TestClient(create_app(load_config(config_path), secret_environment))

    response = client.get("/")

    assert response.headers["content-security-policy"].startswith("default-src 'self'")
    assert response.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_csp_uses_configured_livekit_endpoint(config_path, secret_environment):
    config = load_config(config_path)
    config = config.model_copy(
        update={"ui": config.ui.model_copy(update={"livekit_url": "wss://alternate.example"})}
    )
    client = TestClient(create_app(config, secret_environment))

    response = client.get("/")

    assert "connect-src 'self' wss://alternate.example" in response.headers["content-security-policy"]
