from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable, Mapping
from datetime import timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from livekit import api
from pydantic import BaseModel, ConfigDict

from relate_voice.agent_store import AgentPackage, AgentStore
from relate_voice.config import VoiceAgentConfig, validate_web_secret_references
from relate_voice.provider_catalog import check_provider_health, get_provider_catalog

logger = logging.getLogger("relate_voice.web")

COOKIE_NAME = "relate_voice_session"
DEFAULT_AGENT_STORE = Path("/app/agents")


class SessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    server_url: str
    token: str
    room_name: str
    agent_id: str | None = None
    agent_version: str | None = None


class AgentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id: str
    name: str
    description: str = ""


class AgentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    description: str | None = None
    llm: dict | None = None
    personality: str | None = None
    greeting: str | None = None
    speech: dict | None = None
    turn_handling: dict | None = None
    tools: list[dict] | None = None
    appearance: dict | None = None


class ActivateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id: str


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id: str | None = None


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
    agent_store = AgentStore(os.environ.get("AGENT_STORE_PATH", str(DEFAULT_AGENT_STORE)))

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[config.ui.public_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            f"default-src 'self'; connect-src 'self' {config.ui.livekit_url} {config.ui.public_url}; "
            "media-src 'self' blob:; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'"
        )
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    # ── Health ──

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
            "redis_internal_6379": tcp("redis", 6379),
            "coturn_internal_3478": tcp("coturn", 3478),
        }

    # ── Session (unchanged) ──

    @app.get("/", response_class=FileResponse)
    async def index(request: Request) -> FileResponse:
        result = FileResponse(static_dir / "index.html")
        if not _valid_cookie(request.cookies.get(COOKIE_NAME), session_secret):
            result.set_cookie(
                COOKIE_NAME,
                _cookie_value(session_secret),
                httponly=True,
                secure=True,
                samesite="none",
                max_age=config.ui.rate_window_seconds,
                path="/",
            )
        return result

    @app.get("/assets/{asset_name}")
    async def asset(asset_name: str) -> FileResponse:
        if asset_name not in os.listdir(static_dir / "assets") if (static_dir / "assets").exists() else True:
            if asset_name not in {"main.js", "styles.css"}:
                raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(static_dir / "assets" / asset_name)

    @app.post("/api/session", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
    async def create_session(request: Request) -> SessionResponse:
        if request.headers.get("origin") != config.ui.public_url:
            raise HTTPException(status_code=403, detail="Forbidden")
        client_id = request.headers.get("origin", "unknown")

        now = time.monotonic()
        window = request_times[client_id]
        while window and now - window[0] > config.ui.rate_window_seconds:
            window.popleft()
        if len(window) >= config.ui.max_sessions_per_window:
            raise HTTPException(status_code=429, detail="Session limit reached")
        window.append(now)

        # Resolve active agent
        active_agent = agent_store.get_active_agent()
        agent_id = active_agent.agent_id if active_agent else None
        agent_version = active_agent.version if active_agent else None

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
            agent_id=agent_id,
            agent_version=agent_version,
        )

    # ── Agent CRUD ──

    @app.get("/api/agents")
    async def list_agents() -> list[dict[str, str]]:
        return agent_store.list_agents()

    @app.post("/api/agents", status_code=status.HTTP_201_CREATED)
    async def create_agent(req: AgentCreateRequest) -> dict[str, str]:
        pkg = AgentPackage(agent_id=req.agent_id, name=req.name, description=req.description)
        agent_store.save_agent(pkg)
        return {"agent_id": pkg.agent_id, "status": "created"}

    @app.get("/api/agents/{agent_id}")
    async def get_agent(agent_id: str) -> dict:
        try:
            pkg = agent_store.load_agent(agent_id)
            return pkg.model_dump()
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Agent not found")

    @app.patch("/api/agents/{agent_id}")
    async def update_agent(agent_id: str, req: AgentUpdateRequest) -> dict[str, str]:
        try:
            pkg = agent_store.load_agent(agent_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Agent not found")
        if req.name is not None:
            pkg.name = req.name
        if req.description is not None:
            pkg.description = req.description
        if req.llm is not None:
            from relate_voice.agent_store import LLMProviderConfig
            pkg.llm = LLMProviderConfig(**req.llm)
        if req.personality is not None:
            pkg.personality = req.personality
        if req.greeting is not None:
            pkg.greeting = req.greeting
        if req.speech is not None:
            from relate_voice.agent_store import SpeechConfig
            pkg.speech = SpeechConfig(**req.speech)
        if req.turn_handling is not None:
            from relate_voice.agent_store import TurnHandlingConfig
            pkg.turn_handling = TurnHandlingConfig(**req.turn_handling)
        if req.tools is not None:
            from relate_voice.agent_store import ToolAssignment
            pkg.tools = [ToolAssignment(**t) for t in req.tools]
        if req.appearance is not None:
            from relate_voice.agent_store import AppearanceConfig
            pkg.appearance = AppearanceConfig(**req.appearance)
        agent_store.save_agent(pkg)
        return {"agent_id": agent_id, "status": "updated"}

    @app.delete("/api/agents/{agent_id}")
    async def delete_agent(agent_id: str) -> dict[str, str]:
        agent_store.delete_agent(agent_id)
        return {"agent_id": agent_id, "status": "deleted"}

    @app.post("/api/agents/{agent_id}/duplicate")
    async def duplicate_agent(agent_id: str, req: AgentCreateRequest) -> dict[str, str]:
        try:
            pkg = agent_store.duplicate_agent(agent_id, req.agent_id, req.name)
            return {"agent_id": pkg.agent_id, "status": "duplicated"}
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Source agent not found")

    @app.post("/api/agents/activate")
    async def activate_agent(req: ActivateRequest) -> dict[str, str]:
        try:
            pkg = agent_store.activate_agent(req.agent_id)
            return {"agent_id": pkg.agent_id, "status": "active"}
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Agent not found")

    @app.get("/api/agents/active")
    async def get_active_agent() -> dict:
        pkg = agent_store.get_active_agent()
        if not pkg:
            return {"agent_id": None}
        return pkg.model_dump()

    # ── Import / Export ──

    @app.get("/api/agents/{agent_id}/export")
    async def export_agent(agent_id: str) -> Response:
        try:
            data = agent_store.export_agent(agent_id)
            return Response(
                content=data,
                media_type="application/zip",
                headers={"Content-Disposition": f"attachment; filename={agent_id}.relate-agent.zip"},
            )
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Agent not found")

    @app.post("/api/agents/import", status_code=status.HTTP_201_CREATED)
    async def import_agent(file: UploadFile, agent_id: str | None = None) -> dict[str, str]:
        if not file.filename or not file.filename.endswith(".zip"):
            raise HTTPException(status_code=400, detail="Must be a .zip file")
        data = await file.read()
        try:
            pkg = agent_store.import_agent(data, override_id=agent_id)
            return {"agent_id": pkg.agent_id, "status": "imported"}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    # ── Provider Catalog ──

    @app.get("/api/providers")
    async def list_providers() -> list[dict]:
        return get_provider_catalog()

    @app.get("/api/providers/{provider_id}/health")
    async def provider_health(provider_id: str) -> dict[str, str]:
        return check_provider_health(provider_id, dict(environment))

    # ── Diagnostics ──

    @app.get("/api/diagnostics")
    async def diagnostics() -> dict:
        active = agent_store.get_active_agent()
        return {
            "agent_id": active.agent_id if active else None,
            "agent_version": active.version if active else None,
            "agent_name": active.name if active else None,
            "llm_provider": active.llm.provider if active else None,
            "llm_model": active.llm.model if active else None,
            "stt_provider": active.speech.stt_provider if active else None,
            "stt_model": active.speech.stt_model if active else None,
            "tts_provider": active.speech.tts_provider if active else None,
            "tts_voice": active.speech.tts_voice if active else None,
            "theme": active.appearance.theme if active else None,
            "enabled_tools": [t.tool_id for t in active.tools if t.enabled] if active else [],
            "personality_length": len(active.personality) if active else 0,
            "build_version": os.environ.get("GIT_COMMIT", "unknown"),
        }

    return app
