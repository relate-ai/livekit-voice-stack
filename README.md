# Relate LiveKit Voice Stack

Self-hosted LiveKit voice agent on the Contabo VPS, deployed as one Coolify
Docker Compose application. Browser UI at `https://voice.relate-ai.site`,
LiveKit signalling at `wss://livekit.relate-ai.site`, media relayed over
TURN/TLS on port 443 via `turn.relate-ai.site` (no other inbound ports needed).

## Services

| Service | Role | Public route |
|---|---|---|
| `livekit` | LiveKit Server v1.13.6 (signalling/API) | `https://livekit.relate-ai.site` |
| `redis` | Private state store (AOF persisted) | none |
| `agent` | Python voice worker (Deepgram + OpenRouter) | none |
| `web` | Token/session API + static browser UI | `https://voice.relate-ai.site` |
| `coturn` | TURN relay (TLS terminated at Traefik) | `turns:turn.relate-ai.site:443` (TCP+SNI) |
| `harness` | One-shot scripted conversation validation | none (runs each deploy, then exits) |

## Quick Start (Operator)

1. Ensure Coolify environment variables are set (names in `.env.example`).
   Secrets live ONLY in Coolify; never in git.
2. Deploy through Coolify (Docker Compose build pack, main branch).
3. Open `https://voice.relate-ai.site`, select Start Conversation, allow the
   microphone. The agent greets automatically; speak naturally and interrupt
   freely; select End to hang up.
4. Validate: `GET /api/diag` shows internal listeners; a harness run prints
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

See `OPERATIONS.md`, `PROVIDERS.md`, `COOLIFY_DEPLOYMENT.md`, `TEST_EVIDENCE.md`,
`ROLLBACK.md`.
