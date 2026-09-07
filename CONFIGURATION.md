# Configuration

Application behaviour is defined in `config/voice-agent.yaml` and validated by
`src/relate_voice/config.py` (Pydantic, extra fields forbidden). Public origins
come from required Coolify runtime variables so deployment topology is not
compiled into the image. Invalid provider names, fields, model order, runtime
URLs, or missing secret references fail before the worker accepts jobs.

## Sections

- `stt`: provider (`deepgram`), model (`nova-3`), language, endpoint,
  secret_ref, smart_format, endpointing_ms, mip_opt_out.
- `tts`: provider (`deepgram`), model (`aura-2`), voice (`asteria`), language,
  endpoint, secret_ref, sample_rate, mip_opt_out.
- `llm`: provider (`openrouter`), endpoint, secret_ref, `models` (must equal
  the exact authorised free chain in order), app_name, temperature,
  max_tokens, timeout_seconds.
- `fallback`: eligible HTTP statuses/categories, max attempts per model.
- `turn_handling`: turn_detection (`vad`), endpointing delays, interruption
  (enabled, mode `vad`, min_duration, min_words, false-interruption resume).
- `agent`: dispatch_name, display_name, instructions, greeting.
- `ui`: token TTL (120s) and session rate limits.
- `observability`: log_level, log_model_identity, prometheus_port.

## Swapping Providers

1. Add an adapter implementing the provider protocol in
   `src/relate_voice/providers/` and register it in `registry.py`.
2. Point the corresponding `config/voice-agent.yaml` section at it.
3. No core orchestration changes are needed (covered by mock-injection test).

See `EXTENSION_POINTS.md` for detailed instructions per provider type.

LiveKit network topology (Compose + embedded `configs.livekit.content`) is
deployment configuration, not provider configuration. Coolify owns HTTP/WSS
domains; Compose defines direct media ports, TURN/TLS, Redis, and services.

## Runtime URLs

- `VOICE_PUBLIC_URL`: exact frontend HTTPS origin used for CORS, Origin checks,
  and the OpenRouter site identifier.
- `LIVEKIT_PUBLIC_URL`: public `wss://` signalling origin returned to browsers.

Both values are required Coolify runtime variables and are not stored in the
application configuration file.

## Secrets

Environment variables only (see `.env.example` for names):
`LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `REDIS_PASSWORD`, `WEB_SESSION_SECRET`,
`DEEPGRAM_API_KEY`, `OPENROUTER_API_KEY`, `TURN_SECRET`. The agent uses the
provider and LiveKit credentials; the API uses LiveKit keys plus
`WEB_SESSION_SECRET`; coturn and LiveKit share `TURN_SECRET`.

## Constraints

### LLM Model Chain (Hard-Locked)

The LLM model chain is validated at config load time by
`src/relate_voice/config.py:54-58`:

```python
AUTHORISED_OPENROUTER_MODELS: list[str] = [
    "poolside/laguna-xs-2.1:free",
    "z-ai/glm-5.2:free",
    "cohere/north-mini-code:free",
]
```

If `config/voice-agent.yaml` references a model not in this list, the
application **refuses to start**. This is a security constraint to prevent
accidental use of paid models.

**To add a model:** Edit `AUTHORISED_OPENROUTER_MODELS` in `config.py`.

### Harness Provider Hardcoding

The harness (`src/relate_voice/harness.py`) hardcodes Deepgram API endpoints
and model names (`aura-2-asteria-en`, `nova-3`). It does not use the provider
registry. Changing the STT/TTS provider will break the harness until it is
refactored to use the registry.
