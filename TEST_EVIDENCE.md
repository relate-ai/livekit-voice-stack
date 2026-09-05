# Test Evidence

## Static / Unit (per release)

- `PYTHONPATH=.deps:src python3 -m pytest` (schema, providers, registry,
  agent neutrality, web/token security, Compose topology, harness helpers).
- Ruff, strict mypy (12+ source files), frontend `typecheck` + `build`,
  production `npm audit`.

## Provider Preflight

- Deepgram TTS/STS round-trip on synthetic phrase (HTTP 200 both legs,
  semantic transcript match, confidence recorded).
- OpenRouter: each authorised slug probed; primary/secondary observed
  rate-limited (429) at preflight time, tertiary completed; order preserved.

## Release Runtime (in-network harness, auto-run per deploy)

The `harness` service joins via the token API with explicit agent dispatch,
records agent audio, transcribes via Deepgram, publishes synthesised user
utterances, and asserts: greeting offers help, code-word recall, barge-in
overlap with yield timing, and math answer. Verdict (pass, turns with
transcripts, agent model/provider attributes, barge-in timings) is published
as participant attributes and collected server-side. Reference capture:
room `voice-harness-f73c8047` (4 turns, model
`poolside/laguna-xs-2.1:free`, barge-in yield 4328 ms).

## Media / Browser / Restart

- External PeerConnection via TURN relay proven with an independent client
  (relay pair to internal SFU candidates).
- Browser Start flow: Start -> server token -> join -> mic -> agent greeting.
  Headless-browser automation is unavailable in the build sandbox; the final
  browser confirmation is recorded in `FINAL_INSTALLATION_REPORT.md`.
- Restart/redeploy: rerun connection, turn, barge-in, secret, and neighbour
  checks; see the final report for the release-tied manifest.
