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
