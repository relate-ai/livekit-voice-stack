# Configuration

Single source: `config/voice-agent.yaml`, validated by
`src/relate_voice/config.py` (Pydantic, extra fields forbidden). Invalid
provider names, fields, model order, or missing secret references fail before
the worker accepts jobs.

## Sections

- `stt`: provider (`deepgram`), model (`nova-3`), language, endpoint,
  secret_ref, smart_format, endpointing_ms, mip_opt_out.
- `tts`: provider (`deepgram`), model (`aura-2`), voice (`asteria`), language,
  endpoint, secret_ref, sample_rate, mip_opt_out.
- `llm`: provider (`openrouter`), endpoint, secret_ref, `models` (must equal
  the exact authorised free chain in order), site_url, app_name, temperature,
  max_tokens, timeout_seconds.
- `fallback`: eligible HTTP statuses/categories, max attempts per model.
- `turn_handling`: turn_detection (`vad`), endpointing delays, interruption
  (enabled, mode `vad`, min_duration, min_words, false-interruption resume).
- `agent`: dispatch_name, display_name, instructions, greeting.
- `ui`: public_url, livekit_url, token TTL (120s), session rate limits.
- `observability`: log_level, log_model_identity, prometheus_port.

## Swapping Providers

1. Add an adapter implementing the provider protocol in
   `src/relate_voice/providers/` and register it in `registry.py`.
2. Point the corresponding `config/voice-agent.yaml` section at it.
3. No core orchestration changes are needed (covered by mock-injection test).

LiveKit network topology (Compose + embedded `configs.livekit.content`) is
deployment configuration, not provider configuration: direct media ports,
TURN/TLS route, Redis, and TLS hostnames live in `docker-compose.yml`.

## Secrets

Environment variables only (see `.env.example` for names):
`LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `REDIS_PASSWORD`, `WEB_SESSION_SECRET`,
`DEEPGRAM_API_KEY`, `OPENROUTER_API_KEY`, `TURN_SECRET`. The agent uses the
first five minus `WEB_SESSION_SECRET`; the web service uses LiveKit keys plus
`WEB_SESSION_SECRET`; coturn and LiveKit share `TURN_SECRET`.
