from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable, Mapping
from datetime import timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from livekit import api
from pydantic import BaseModel, ConfigDict

from relate_voice.config import VoiceAgentConfig, validate_web_secret_references

COOKIE_NAME = "relate_voice_session"


class SessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    server_url: str
    token: str
    room_name: str


def _cookie_value(secret: str) -> str:
    nonce = secrets.token_urlsafe(24)
    signature = hmac.new(secret.encode(), nonce.encode(), hashlib.sha256).digest()
    return f"{nonce}.{base64.urlsafe_b64encode(signature).decode().rstrip('=')}"


def _valid_cookie(value: str | None, secret: str) -> bool:
    if not value or "." not in value:
        return False
    nonce, supplied = value.rsplit(".", 1)
    expected = _cookie_value_for_nonce(nonce, secret)
    return hmac.compare_digest(value, expected)


def _cookie_value_for_nonce(nonce: str, secret: str) -> str:
    signature = hmac.new(secret.encode(), nonce.encode(), hashlib.sha256).digest()
    return f"{nonce}.{base64.urlsafe_b64encode(signature).decode().rstrip('=')}"


def create_app(
    config: VoiceAgentConfig,
    environment: Mapping[str, str],
    static_dir: Path | None = None,
) -> FastAPI:
    validate_web_secret_references(environment)
    static_dir = static_dir or Path(__file__).parents[2] / "web"
    session_secret = environment["WEB_SESSION_SECRET"]
    request_times: dict[str, deque[float]] = defaultdict(deque)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            f"default-src 'self'; connect-src 'self' {config.ui.livekit_url}; "
            "media-src 'self' blob:; img-src 'self' data:; style-src 'self'; script-src 'self'"
        )
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/healthz")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/diag")
    async def diag() -> dict[str, object]:
        import socket as _socket

        def tcp(host: str, port: int) -> dict[str, object]:
            sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
            sock.settimeout(3)
            try:
                sock.connect((host, port))
                return {"open": True}
            except Exception as exc:
                return {"open": False, "error": type(exc).__name__}
            finally:
                sock.close()

        return {
            "livekit_internal_7880": tcp("livekit", 7880),
            "livekit_internal_7881": tcp("livekit", 7881),
            "redis_internal_6379": tcp("redis", 6379),
            "host_hairpin_7881": tcp("37.60.235.136", 7881),
        }

    @app.get("/", response_class=FileResponse)
    async def index(request: Request) -> FileResponse:
        result = FileResponse(static_dir / "index.html")
        if not _valid_cookie(request.cookies.get(COOKIE_NAME), session_secret):
            result.set_cookie(
                COOKIE_NAME,
                _cookie_value(session_secret),
                httponly=True,
                secure=True,
                samesite="strict",
                max_age=config.ui.rate_window_seconds,
                path="/",
            )
        return result

    @app.get("/assets/{asset_name}")
    async def asset(asset_name: str) -> FileResponse:
        if asset_name not in {"main.js", "styles.css"}:
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(static_dir / "assets" / asset_name)

    @app.post("/api/session", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
    async def create_session(request: Request) -> SessionResponse:
        if request.headers.get("origin") != config.ui.public_url:
            raise HTTPException(status_code=403, detail="Forbidden")
        cookie = request.cookies.get(COOKIE_NAME)
        if cookie is None or not _valid_cookie(cookie, session_secret):
            raise HTTPException(status_code=403, detail="Forbidden")

        now = time.monotonic()
        window = request_times[cookie]
        while window and now - window[0] > config.ui.rate_window_seconds:
            window.popleft()
        if len(window) >= config.ui.max_sessions_per_window:
            raise HTTPException(status_code=429, detail="Session limit reached")
        window.append(now)

        room_name = f"voice-{uuid.uuid4().hex}"
        identity = f"browser-{uuid.uuid4().hex}"
        token = (
            api.AccessToken(environment["LIVEKIT_API_KEY"], environment["LIVEKIT_API_SECRET"])
            .with_identity(identity)
            .with_grants(
                api.VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=True,
                    can_subscribe=True,
                    can_publish_data=False,
                    can_publish_sources=["microphone"],
                )
            )
            .with_room_config(
                api.RoomConfiguration(agents=[api.RoomAgentDispatch(agent_name=config.agent.dispatch_name)])
            )
            .with_ttl(timedelta(seconds=config.ui.token_ttl_seconds))
            .to_jwt()
        )
        return SessionResponse(
            server_url=config.ui.livekit_url,
            token=token,
            room_name=room_name,
        )

    return app
