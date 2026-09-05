# Providers

## Deepgram STT

Streaming transcription (`nova-3`, `en-US`, smart format, 300 ms endpointing)
via `livekit-plugins-deepgram`. Preflight: known-phrase audio transcribes with
high confidence; release proof: scripted user utterances transcribed through
the deployed pipeline (see `TEST_EVIDENCE.md`).

## Deepgram TTS

Streaming synthesis (`aura-2-asteria-en`, 24 kHz) via the same plugin.
Preflight: HTTP 200 with playable bytes; release proof: agent greeting and
replies received as subscribed audio frames and transcribed back.

## OpenRouter LLM (free-only chain)

Order enforced by schema: `poolside/laguna-xs-2.1:free`, then
`z-ai/glm-5.2:free`, then `cohere/north-mini-code:free`. The adapter passes
the chain as primary plus ordered fallbacks. Fallback engages only for
rate-limit, timeout, transient, or unavailable-model failures; auth,
invalid-request, configuration, and code errors fail fast and loud.

Runtime model identity is attested per session: the worker publishes
`relate_active_llm_model` / `relate_active_llm_provider` participant
attributes from the first LLM metric. The release harness reads these back and
asserts membership in the authorised chain. No paid or unlisted model is
reachable: schema forbids it and the factory test asserts the reachable set
equals the exact chain.

## Mock Providers

`providers/mock.py` builds inert providers for any role, proving the registry
extends without touching `agent.py` (unit-tested).
