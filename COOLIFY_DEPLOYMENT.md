# Coolify Deployment

## Two-Application Architecture

The system runs as two independent Coolify applications on a single VPS:

### Frontend — Relate Voice UI

- **Coolify UUID:** `ps7z244qvspp3by5sdlcrlc8`
- **Project:** Web Apps (`sejk5tyw2y2i6xheotx35rw5`)
- **Build pack:** Dockerfile (multi-stage: node build → nginx serve)
- **Repository:** `relate-ai/relate-voice-ui`, branch `main`
- **Domain:** `https://voice.relate-ai.site`
- **Port:** 8080 (nginx)
- **No secrets** — only serves static files

### Backend — Relate LiveKit Voice

- **Coolify UUID:** `xa0mj8kgd9ydkzg89pzdgz13`
- **Project:** AI Agents (`ojecnja8ugw30vq4clv53lr6`), environment `livekit`
- **Build pack:** Docker Compose from `relate-ai/livekit-voice-stack`
- **Branch:** `main` (production) / `modularization/frontend-separation` (active dev)
- **Domains:**
  - `livekit` service port 7880 → `https://livekit.relate-ai.site`
  - `web` service port 8000 → `https://voice-api.relate-ai.site`
- **Direct host ports:** `7881/tcp` (ICE/TCP), `7882/udp` (UDP mux)
  Currently blocked by host firewall; all client media uses TURN/TLS on 443.

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
| `LIVEKIT_API_KEY` | agent, web, api | LiveKit authentication |
| `LIVEKIT_API_SECRET` | agent, web, api | LiveKit token signing |
| `DEEPGRAM_API_KEY` | agent, harness | Deepgram STT/TTS |
| `OPENROUTER_API_KEY` | agent | OpenRouter LLM chain |
| `REDIS_PASSWORD` | redis, livekit | Redis auth |
| `TURN_SECRET` | coturn, livekit | TURN credential generation |
| `WEB_SESSION_SECRET` | web, api | Session cookie signing |

## Reproducing / Restarting

- Redeploy the pinned commit through Coolify to rebuild and revalidate
  (the harness runs automatically; collect its verdict attributes).
- Restart keeps images and re-runs healthchecks; Redis data persists in the
  `redis-data` volume.
- Frontend deploys are independent — they never restart backend containers.

## Rollback

- **Tag:** `relate-livekit-voice-baseline-9c8823b`
- **Commit:** `9c8823b71a340f5749c1a6315defd671b5ffda61`
- Restores the pre-modularization single-compose state
