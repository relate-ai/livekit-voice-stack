# Operations

## Health Signals

- `GET https://voice.relate-ai.site/healthz` -> `{"status":"ok"}` (web).
- `GET https://voice.relate-ai.site/api/diag` -> internal listener states
  (LiveKit 7880/7881, coturn 3478 + STUN, Redis 6379) and hairpin observations.
- Coolify application status should be `running:healthy`.
- Harness verdict: after each deploy, a `voice-harness-*` room appears; read
  participant attributes `relate_harness_done=true` plus
  `relate_harness_0..N` chunks for the full conversation verdict.

## Logs

Coolify log view returns the web container. Agent/worker logs are visible in
the Coolify web terminal or `docker logs` on the host. Application logs never
contain secret values or prompt text (model slugs and timings only).

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| Browser stuck at Connecting | TURN/TLS or signalling down | Check `/api/diag`, `turn.relate-ai.site:443` TLS, Coolify status |
| Agent never joins | Worker unregistered / LLM outage | Dispatch probe room via API; check provider status |
| No audio either way | ICE blocked | Confirm relay candidates in client logs; check coturn health |
| 429s from OpenRouter | Free-tier quota | Wait for reset; fallback chain advances automatically |
| Deploy fails at build | Build-time env gap | Keep runtime-only secrets out of parse-time (`:-` defaults) |

## Rollback

See `ROLLBACK.md` and the durable rollback record in the execution cache.

## Post-Deployment Verification Checklist

Run these after every deployment or when diagnosing issues.

### Infrastructure

- [ ] DNS: `dig voice.relate-ai.site +short` returns VPS IP
- [ ] DNS: `dig voice-api.relate-ai.site +short` returns VPS IP
- [ ] DNS: `dig livekit.relate-ai.site +short` returns VPS IP
- [ ] DNS: `dig turn.relate-ai.site +short` returns VPS IP
- [ ] TLS: `curl -sk -o /dev/null -w "%{http_code}" https://voice.relate-ai.site/` returns 200
- [ ] TLS: `curl -sk -o /dev/null -w "%{http_code}" https://voice-api.relate-ai.site/healthz` returns 200
- [ ] TURN: `openssl s_client -connect turn.relate-ai.site:443` shows valid cert

### Backend Services

- [ ] Coolify status: `running:healthy`
- [ ] Healthz: `curl -sk https://voice-api.relate-ai.site/healthz` returns `{"status":"ok"}`
- [ ] Diag: `curl -sk https://voice-api.relate-ai.site/api/diag` shows:
  - `livekit_internal_7880: open`
  - `livekit_internal_7881: open`
  - `coturn_internal_3478: open`
  - `coturn_internal_stun: stun_binding_response: true`
  - `redis_internal_6379: open`

### Frontend

- [ ] Coolify status: `running:healthy`
- [ ] Page loads: `curl -sk https://voice.relate-ai.site/` contains `<title>Relate Voice AI</title>`
- [ ] JS bundle: `curl -sk https://voice.relate-ai.site/assets/main.js` returns 200

### Session Flow

- [ ] POST session: `curl -sk -X POST https://voice-api.relate-ai.site/api/session -H "Origin: https://voice.relate-ai.site"` returns `{"server_url":"...","token":"...","room_name":"..."}`

### Browser End-to-End

- [ ] Open `https://voice.relate-ai.site`
- [ ] Click **Start Conversation**
- [ ] Allow microphone
- [ ] Status changes to "Listening" within 5 seconds
- [ ] Speak — agent responds with audio
- [ ] Interrupt mid-sentence — agent stops and listens (barge-in)
- [ ] Click **End** — clean disconnect, status returns to "Ready"

### Harness (Automatic)

- [ ] After backend deploy, check Coolify logs (source: `harness`)
- [ ] Look for `HARNESS_RESULT` in output
- [ ] Verify `relate_harness_done=true` in room participant attributes
