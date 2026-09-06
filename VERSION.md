# Version Inventory

Complete version manifest for the Relate LiveKit Voice Stack.
Every dependency, runtime, and infrastructure component with its exact version.

**Last verified:** 2026-09-06

---

## Runtime Versions

| Component | Version | Source | Notes |
|---|---|---|---|
| Python | ≥3.11, <3.14 | `pyproject.toml:5` | Dockerfile pins exact image by digest |
| Node.js | digest-pinned | `Dockerfile.web:1` | No explicit version tag; see Docker image table |
| nginx | 1.27.3-alpine | `Dockerfile:10` | Frontend static server |
| LiveKit Server | 1.13.6 | `README.md:32`, `ARCHITECTURE.md:44` | Docker image digest-pinned |
| Redis | 7.x (digest-pinned) | `docker-compose.yml:3` | AOF persisted |
| coturn | 4.x (digest-pinned) | `docker-compose.yml:45` | TURN relay |
| Coolify | 4.0.0 | Container labels | Deployment platform |
| Traefik | 3.1.7 | Coolify server metadata | Reverse proxy (outdated; latest 3.7.8) |

## Docker Images

All images are digest-pinned for reproducibility. No mutable tags.

| Image | Digest | Used By |
|---|---|---|
| `redis` | `sha256:0302ccce...` | redis service |
| `livekit/livekit-server` | `sha256:e37d68f1...` | livekit service |
| `coturn/coturn` | `sha256:908d0295...` | coturn service |
| `python` (base) | `sha256:78144946...` | agent, web, api Dockerfiles |
| `node` (build stage) | `sha256:7eb2c0c4...` | web, relate-voice-ui Dockerfiles |
| `nginx:1.27.3-alpine` | tag-pinned | relate-voice-ui runtime |

## Python Dependencies (Direct)

From `pyproject.toml` — exact-pinned:

| Package | Version | Purpose |
|---|---|---|
| `fastapi` | 0.141.1 | Gateway HTTP framework |
| `livekit-agents` | 1.8.0 | Voice agent SDK |
| `livekit-api` | 1.2.1 | LiveKit server API client |
| `livekit-plugins-deepgram` | 1.8.0 | Deepgram STT/TTS plugin |
| `livekit-plugins-openai` | 1.8.0 | OpenAI-compatible LLM plugin (used for OpenRouter) |
| `pydantic` | 2.13.5 | Config schema validation |
| `PyYAML` | 6.0.3 | YAML config parsing |
| `uvicorn[standard]` | 0.52.4 | ASGI server |

## Python Dependencies (Dev)

| Package | Version | Purpose |
|---|---|---|
| `httpx` | 0.28.1 | HTTP client for tests |
| `httpx2` | 2.12.0 | Extended HTTP client |
| `mypy` | 2.3.1 | Static type checker |
| `pytest` | 9.1.1 | Test framework |
| `ruff` | 0.16.6 | Linter/formatter |
| `types-PyYAML` | 6.0.12.20260815 | YAML type stubs |

## Frontend Dependencies

From `relate-voice-ui/package.json`:

| Package | Version | Purpose |
|---|---|---|
| `livekit-client` | 2.22.2 | Browser LiveKit SDK |
| `esbuild` | 0.25.9 | JavaScript bundler |
| `typescript` | 7.0.2 | Type checker |

## API Models (LLM Chain)

Configured in `config/voice-agent.yaml` — free-tier only:

| Model | Provider | Status |
|---|---|---|
| `poolside/laguna-xs-2.1:free` | OpenRouter | Primary |
| `z-ai/glm-5.2:free` | OpenRouter | Fallback 1 |
| `cohere/north-mini-code:free` | OpenRouter | Fallback 2 |

**Constraint:** The LLM model chain is hard-locked in `config.py:54-58`.
Only these three models are authorised. To use a different model, you must
modify `AUTHORISED_OPENROUTER_MODELS` in `src/relate_voice/config.py`.

## STT/TTS Models

| Component | Provider | Model | Endpoint |
|---|---|---|---|
| STT | Deepgram | `nova-3` | `https://api.deepgram.com/v1/listen` |
| TTS | Deepgram | `aura-2` (voice: `asteria`) | `https://api.deepgram.com/v1/speak` |

## Project Versions

| Component | Version | Source |
|---|---|---|
| relate-livekit-voice (backend) | 0.1.0 | `pyproject.toml:3` |
| relate-livekit-voice-ui (frontend) | 0.1.0 | `package.json:3` |
| Profile schema | 1 | `src/relate_voice/profiles/loader.py:10` |

## Infrastructure

| Component | Value |
|---|---|
| VPS Provider | Contabo VPS 30 |
| VPS Specs | 8 vCPU / 24 GB RAM / 200 GB NVMe |
| VPS IP | 37.60.235.136 |
| OS | Ubuntu (Coolify-managed) |
| Coolify Version | 4.0.0 |
| Traefik Version | 3.1.7 |
| DNS Provider | Hostinger |
| SSL Provider | Let's Encrypt (via Traefik) |

## Rollback Baseline

| Item | Value |
|---|---|
| Tag | `relate-livekit-voice-baseline-9c8823b` |
| Commit | `9c8823b71a340f5749c1a6315defd671b5ffda61` |
| Branch | `main` |
| Date | 2026-09-05 |
