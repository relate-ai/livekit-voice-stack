# Coolify Deployment

## Two-Application Architecture

The system runs as two independent Coolify applications on a single VPS:

### Frontend — Relate Voice UI

- **Project:** Web Apps
- **Build pack:** Dockerfile (multi-stage: node build → nginx serve)
- **Repository:** `relate-ai/relate-voice-ui`, branch `main`
- **Domain:** `https://voice.relate-ai.site`
- **Port:** 8080 (nginx)
- **Runtime configuration:** `VOICE_API_URL` contains the API HTTPS origin
- **No secrets** — only serves static files and a non-secret runtime URL

### Backend — Relate LiveKit Voice

- **Project:** AI Agents, environment `livekit`
- **Build pack:** Docker Compose from `relate-ai/livekit-voice-stack`
- **Branch:** `main` (production) / `modularization/frontend-separation` (active dev)
- **Domains:**
  - `livekit` service port 7880 → `https://livekit.relate-ai.site`
  - `api` service port 8000 → `https://voice-api.relate-ai.site`
- **Direct host ports:** `7881/tcp` (ICE/TCP), `7882/udp` (UDP mux)
  Currently blocked by host firewall; all client media uses TURN/TLS on 443.

Assign these domains through each service's standard Coolify **Domains**
configuration. Do not add application-managed Traefik HTTP labels or fixed
`SERVICE_FQDN_*` values to Compose.

## TCP+SNI Route (TURN/TLS)

Custom labels on `coturn` map `HostSNI(turn.relate-ai.site)` on entrypoint
`https` to coturn:3478 with Traefik TLS termination (`letsencrypt`). Requires
the `traefik.enable=true` label (Coolify only adds it to domain-routed
services). TCP routers apply before HTTP routers and fall through on SNI
mismatch, so existing HTTPS routes are unaffected.

## DNS (Hostinger)

| Record | Type | Value | TTL |
|---|---|---|---|
| `livekit` | A | `37.60.235.136` | 300 |
| `voice` | A | `37.60.235.136` | 300 |
| `turn` | A | `37.60.235.136` | 300 |
| `voice-api` | A | `37.60.235.136` | 300 |

## Secrets

Set the following as Coolify runtime (shown-once) variables. Never commit
values to git.

| Variable | Service | Purpose |
|---|---|---|
| `LIVEKIT_API_KEY` | agent, api | LiveKit authentication |
| `LIVEKIT_API_SECRET` | agent, api | LiveKit token signing |
| `DEEPGRAM_API_KEY` | agent, harness | Deepgram STT/TTS |
| `OPENROUTER_API_KEY` | agent | OpenRouter LLM chain |
| `REDIS_PASSWORD` | redis, livekit | Redis auth |
| `TURN_SECRET` | coturn, livekit | TURN credential generation |
| `WEB_SESSION_SECRET` | api | Session cookie signing |

## Runtime Configuration

Set these non-secret values in the normal Coolify environment-variable UI.
They persist independently of container replacement.

| Application | Variable | Purpose |
|---|---|---|
| Relate Voice UI | `VOICE_API_URL` | HTTPS origin assigned to `api:8000` |
| Relate LiveKit Voice | `VOICE_PUBLIC_URL` | Exact frontend HTTPS origin used by CORS and session Origin checks |
| Relate LiveKit Voice | `LIVEKIT_PUBLIC_URL` | Public `wss://` signalling origin returned to browsers |

`AGENT_STORE_PATH` is container-local configuration fixed at `/app/agents` in
Compose. The `agent-data` named volume is mounted there for both the API writer
and agent reader; no host path or manual directory is required.

## Reproducing / Restarting

- Redeploy the pinned commit through Coolify to rebuild and revalidate
  (the harness runs automatically; collect its verdict attributes).
- Restart keeps images and re-runs healthchecks. Redis and agent data persist
  in the Compose-managed `redis-data` and `agent-data` named volumes.
- Frontend deploys are independent — they never restart backend containers.

## Rollback

- **Tag:** `relate-livekit-voice-baseline-9c8823b`
- **Commit:** `9c8823b71a340f5749c1a6315defd671b5ffda61`
- Restores the pre-modularization single-compose state
