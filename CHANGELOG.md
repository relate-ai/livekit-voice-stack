# Changelog

All notable changes to the Relate LiveKit Voice Stack.
Format: Keep a Changelog.

---

## [0.1.0] — 2026-09-06

### Initial Production Release

#### Added
- **LiveKit Server** signalling at `wss://livekit.relate-ai.site`
- **Voice Agent** with Deepgram STT/TTS and OpenRouter LLM chain
- **TURN/TLS** media relay via coturn + Traefik TCP/SNI at `turn.relate-ai.site`
- **Gateway** (FastAPI) for session/token issuance at `voice-api.relate-ai.site`
- **Frontend** (nginx + LiveKit client) at `voice.relate-ai.site`
- **Provider registry** pattern for swappable STT/TTS/LLM providers
- **Config schema** validation via Pydantic + single YAML source
- **Free-tier LLM chain** with automatic fallback (rate-limit/timeout/transient)
- **VAD turn detection** with interruption and barge-in
- **Harness** for automated conversation validation
- **CORS** support for cross-origin frontend→backend calls
- **Coolify deployment** as two independent applications

#### Architecture
- Two-application topology: frontend (Coolify Web Apps) + backend (Coolify AI Agents)
- Frontend calls backend API directly (CORS-enabled, no nginx proxy)
- All secrets in Coolify runtime variables (never in git)
- All Docker images digest-pinned for reproducibility
- All Python dependencies exact-pinned in `requirements.lock.txt`

#### Documentation
- `INSTALL.md` — from-scratch installation guide (bare VPS → working deploy)
- `ARCHITECTURE.md` — topology, media path, session flow, domain routing
- `VERSION.md` — complete version inventory
- `EXTENSION_POINTS.md` — how to modify persona, providers, tools
- `CONFIGURATION.md` — config schema and provider swap instructions
- `OPERATIONS.md` — health signals, troubleshooting, verification checklist
- `COOLIFY_DEPLOYMENT.md` — Coolify setup, DNS, secrets, TCP/SNI
- `PROVIDERS.md` — STT/TTS/LLM provider details
- `ROLLBACK.md` — rollback procedure
- `TEST_EVIDENCE.md` — test results and validation

#### Known Limitations
- LLM model chain hard-locked to 3 free models (requires code change to modify)
- Tool/MCP integration planned but not implemented
- Harness hardcoded to Deepgram (not portable to other STT providers)
- Node.js version not explicitly documented (digest-pinned only)
- Traefik 3.1.7 (outdated; latest 3.7.8)
