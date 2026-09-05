# LiveKit Voice Stack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy and prove an isolated, provider-neutral self-hosted LiveKit voice-agent stack through Coolify and Hostinger.

**Architecture:** One Coolify Compose resource contains four isolated containers: LiveKit, Redis, agent, and web/token UI. A schema-validated Python provider registry supplies Deepgram STT/TTS and an OpenRouter-only LLM chain to provider-neutral LiveKit session orchestration.

**Tech Stack:** LiveKit Server, LiveKit Agents Python, FastAPI, Pydantic, Redis, TypeScript/Vite, Playwright, Docker Compose, Coolify API, Hostinger DNS API.

## Global Constraints

- Only `poolside/laguna-xs-2.1:free`, `z-ai/glm-5.2:free`, and `cohere/north-mini-code:free`, in that order, may be reachable.
- Secrets remain in environment variables and Coolify secret storage only.
- Every behaviour change follows RED, GREEN, REFACTOR.
- No existing Coolify or DNS resource may be modified for convenience.
- Runtime success requires final-state evidence after Coolify restart.
- Embedded TURN is explicitly disabled; Compose may publish only `7881/tcp` and `7882/udp` for media.

---

### Task 1: Durable Execution State And Discovery

**Files:**
- Create: `/data/working/opencode/progress/livekit-install/*`
- Create: `docs/decisions/0001-single-compose-topology.md`

**Interfaces:**
- Consumes: frozen user contract and live control-plane APIs.
- Produces: atomic cache, resource baseline, collision matrix, rollback targets, and architecture decision.

- [ ] Write cache validation tests for required fields, allowed scorecard states, and secret-value rejection.
- [ ] Run the tests and verify they fail because the cache validator is absent.
- [ ] Implement the cache validator and initial state files.
- [ ] Run cache tests and verify they pass.
- [ ] Record read-only Coolify, Hostinger, DNS, domain, status, and capacity evidence.
- [ ] Commit the project-local design and state tooling.

### Task 2: Provider Preflight And Configuration

**Files:**
- Create: `config/voice-agent.yaml`
- Create: `src/voice_agent/config.py`
- Create: `src/voice_agent/providers/{base,registry,deepgram,openrouter,mock}.py`
- Test: `tests/unit/test_config.py`
- Test: `tests/unit/test_providers.py`

**Interfaces:**
- Consumes: secret references `DEEPGRAM_API_KEY` and `OPENROUTER_API_KEY`.
- Produces: `VoiceAgentConfig`, `ProviderRegistry`, STT/TTS/LLM instances, and classified fallback events.

- [ ] Write failing tests that reject missing sections, unknown providers/fields, duplicate or reordered models, non-free/unlisted models, and missing secret references.
- [ ] Run those tests and confirm expected failures.
- [ ] Implement the strict Pydantic schema and YAML loader.
- [ ] Run configuration tests and confirm passing results.
- [ ] Write failing tests for registry construction, mock injection, ordered fallback, retryable categories, and non-retryable errors.
- [ ] Implement minimal provider protocols, adapters, registry, and fallback wrapper.
- [ ] Run provider tests and all earlier tests.
- [ ] Probe Deepgram TTS/STT and each listed OpenRouter model with non-sensitive synthetic input; persist only redacted status/model metadata.
- [ ] Commit configuration and provider layer.

### Task 3: Provider-Neutral Agent

**Files:**
- Create: `src/voice_agent/agent.py`
- Create: `src/voice_agent/main.py`
- Test: `tests/unit/test_agent.py`

**Interfaces:**
- Consumes: `VoiceAgentConfig` and provider instances from `ProviderRegistry`.
- Produces: LiveKit `AgentSession` with automatic endpointing and interruption.

- [ ] Write failing tests proving core orchestration takes injected providers and contains no provider slug branching.
- [ ] Write failing tests for turn/interruption settings and greeting behaviour.
- [ ] Implement minimal LiveKit session assembly with SDK-native VAD and interruption primitives.
- [ ] Run agent and full unit tests.
- [ ] Commit provider-neutral orchestration.

### Task 4: Secure Token API And Browser UI

**Files:**
- Create: `src/web/app.py`
- Create: `web/{index.html,src/main.ts,src/styles.css,package.json,package-lock.json,vite.config.ts}`
- Test: `tests/unit/test_web.py`
- Test: `web/tests/conversation.spec.ts`

**Interfaces:**
- Consumes: LiveKit server URL, API credentials, dispatch name, and UI configuration.
- Produces: `POST /api/session`, static HTTPS UI, and one-action browser join flow.

- [ ] Write failing API tests for strict input, generated identities, room-scoped short TTL grants, rate limits, security headers, and secret-free responses.
- [ ] Implement the FastAPI endpoint and static serving.
- [ ] Run API tests.
- [ ] Write failing Playwright tests for Start, browser permission, state transitions, actionable errors, and End.
- [ ] Implement the minimal client with microphone publication and remote audio playback.
- [ ] Run TypeScript, build, and browser tests.
- [ ] Commit web/token slice.

### Task 5: Reproducible Containers And Deployment

**Files:**
- Create: `Dockerfile.agent`, `Dockerfile.web`, `docker-compose.yml`, `.env.example`, `.gitignore`
- Test: `tests/static/test_compose.py`

**Interfaces:**
- Consumes: pinned dependencies, built web assets, and Coolify environment secret references.
- Produces: a Coolify-compatible Compose definition with two HTTPS routes and direct media ports.

- [ ] Write failing Compose tests for pinning, health checks, private services, least privilege, log caps, persistence, explicit TURN disablement, and an exact `7881/tcp` plus `7882/udp` direct-port allowlist.
- [ ] Implement minimal container and Compose files.
- [ ] Run static tests, image builds, and local health smoke tests.
- [ ] Commit reproducible deployment sources and record the release commit.
- [ ] Create an additive Coolify service with environment values through the API.
- [ ] Create only missing Hostinger A records by API and persist returned identifiers.
- [ ] Poll bounded deployment, DNS, TLS, and health states.

### Task 6: Deployed Release Tests And Restart

**Files:**
- Create: `tests/release/*`
- Create: `scripts/release-test.sh`
- Create: `README.md`, `ARCHITECTURE.md`, `CONFIGURATION.md`, `PROVIDERS.md`, `COOLIFY_DEPLOYMENT.md`, `OPERATIONS.md`, `TEST_EVIDENCE.md`, `ROLLBACK.md`, `FINAL_INSTALLATION_REPORT.md`

**Interfaces:**
- Consumes: deployed release commit/config hash/resource IDs.
- Produces: semantic release-test evidence and terminal scorecard.

- [ ] Run control-plane/DNS, WSS join, media publication, known-audio STT, actual-model/fallback, TTS audio, three-turn, barge-in, browser, secret, and neighbour-preservation tests.
- [ ] Correct only evidence-supported defects, with at most three internal iterations per unchanged defect.
- [ ] Restart the service through Coolify and rerun critical runtime tests.
- [ ] Scan Git, browser bundle, cache, evidence, and ordinary logs for actual secrets.
- [ ] Finalise operator/provider-swap/rollback documentation and release manifest.
- [ ] Reconcile live state with cache, freeze scorecard/status, append process learning, and commit final documentation.
