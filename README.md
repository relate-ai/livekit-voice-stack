# Relate LiveKit Voice Stack

Self-hosted LiveKit voice agent on a Contabo VPS, deployed as two independent
Coolify applications. Browser UI at `https://voice.relate-ai.site`, LiveKit
signalling at `wss://livekit.relate-ai.site`, media relayed over TURN/TLS on
port 443 via `turn.relate-ai.site` (no other inbound ports needed).

## Repositories

| Repository | Branch | Role |
|---|---|---|
| `relate-ai/relate-voice-ui` | `main` | Static frontend (nginx) |
| `relate-ai/livekit-voice-stack` | `main` | Backend stack (LiveKit + agent + gateway) |

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for full topology, media path,
conversation flow, and domain routing.

## Services

### Frontend (Coolify Web Apps)

| Service | Role | Public route |
|---|---|---|
| `voice-ui` | nginx serving static SPA | `https://voice.relate-ai.site` |

### Backend (Coolify AI Agents)

| Service | Role | Public route |
|---|---|---|
| `livekit` | LiveKit Server v1.13.6 (signalling/API) | `https://livekit.relate-ai.site` |
| `redis` | Private state store (AOF persisted) | none |
| `agent` | Python voice worker (Deepgram + OpenRouter) | none |
| `web` | Token/session gateway (FastAPI) | `https://voice-api.relate-ai.site` |
| `api` | Dedicated API service (FastAPI) | internal |
| `coturn` | TURN relay (TLS terminated at Traefik) | `turns:turn.relate-ai.site:443` |
| `harness` | One-shot scripted conversation validation | none (exits after deploy) |

## Quick Start (Operator)

**New install?** Follow [INSTALL.md](INSTALL.md) for the complete
from-scratch procedure (Coolify setup, DNS, secrets, deployment, verification).

1. Ensure Coolify environment variables are set (names in `.env.example`).
   Secrets live ONLY in Coolify; never in git.
2. Deploy backend through Coolify (Docker Compose build pack, `main` branch).
3. Deploy frontend through Coolify (Dockerfile build pack, `main` branch).
4. Open `https://voice.relate-ai.site`, select Start Conversation, allow the
   microphone. The agent greets automatically; speak naturally and interrupt
   freely; select End to hang up.
5. Validate: `GET /api/diag` shows internal listeners; a harness run prints
   `HARNESS_RESULT` and stores verdict attributes on its room participant.

## Configuration

Single file: `config/voice-agent.yaml` (schema-validated, see
`CONFIGURATION.md`). Swap STT/TTS/LLM providers, models, voices, endpoints,
timeouts, turn handling, and UI settings there. Secrets are referenced by
environment-variable NAME only.

## Tests

- `PYTHONPATH=.deps:src python3 -m pytest` (unit + static Compose tests)
- `.lint-deps/bin/ruff check src tests`, strict `mypy`, `npm run typecheck/build`
- In-network harness: `python -m relate_voice.harness` (inside deployment only)

## Documentation

| File | Contents |
|---|---|
| `INSTALL.md` | **Full from-scratch installation guide** (bare VPS → working deploy) |
| `ARCHITECTURE.md` | Topology, media path, conversation flow, domain routing |
| `CONFIGURATION.md` | Config schema, all settings, provider options |
| `COOLIFY_DEPLOYMENT.md` | Coolify setup, DNS, secrets, reproducing |
| `OPERATIONS.md` | Day-to-day operations, monitoring, troubleshooting |
| `PROVIDERS.md` | STT/TTS/LLM provider details and fallback chain |
| `TEST_EVIDENCE.md` | Test results and validation evidence |
| `ROLLBACK.md` | Rollback procedure and baseline tag |
