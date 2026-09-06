# Extension Points

Where and how to modify every aspect of the Relate LiveKit Voice Stack.
Each section tells you: what file to edit, what to change, and what breaks if you get it wrong.

---

## Change the Agent Persona / Instructions

**File:** `config/voice-agent.yaml` lines 51–52

```yaml
agent:
  dispatch_name: relate-voice-agent
  display_name: Relate Voice
  instructions: You are a concise, warm voice assistant. Use short spoken answers without markdown.
  greeting: Greet the user briefly and ask how you can help.
```

- `instructions` — system prompt for the LLM (1–4000 chars, validated)
- `greeting` — first thing the agent says when a session starts

**No code changes required.** Edit the YAML, redeploy.

**Schema:** Validated by `src/relate_voice/config.py:91-92` (`AgentConfig`).

---

## Swap the STT Provider

**Files to modify:**
1. `src/relate_voice/providers/` — create new file (e.g., `assemblyai.py`)
2. `src/relate_voice/providers/registry.py` — register the new factory
3. `config/voice-agent.yaml` — update `stt:` section

**Step 1: Create adapter**

```python
# src/relate_voice/providers/assemblyai.py
from relate_voice.providers.base import ProviderFactory

def build_stt(spec, environment):
    # Import your provider's LiveKit plugin
    from livekit.plugins import assemblyai
    return assemblyai.STT(api_key=environment["ASSEMBLYAI_API_KEY"])
```

**Step 2: Register**

```python
# src/relate_voice/providers/registry.py
from relate_voice.providers.assemblyai import build_stt

registry.register("stt", "assemblyai", build_stt)
```

**Step 3: Update config**

```yaml
stt:
  provider: assemblyai
  model: best
  secret_ref: ASSEMBLYAI_API_KEY
```

**What breaks:** If the new provider doesn't implement the LiveKit `STT` protocol, the agent will crash at startup.

---

## Swap the TTS Provider

Same pattern as STT.

**Files to modify:**
1. `src/relate_voice/providers/` — create new file
2. `src/relate_voice/providers/registry.py` — register
3. `config/voice-agent.yaml` — update `tts:` section

**Current TTS:** Deepgram `aura-2` with voice `asteria`.

**Example: ElevenLabs**

```python
# src/relate_voice/providers/elevenlabs.py
def build_tts(spec, environment):
    from livekit.plugins import elevenlabs
    return elevenlabs.TTS(api_key=environment["ELEVENLABS_API_KEY"])
```

**What breaks:** If the new provider doesn't implement the LiveKit `TTS` protocol, the agent will crash at startup. Audio quality and latency depend on the provider.

---

## Swap the LLM Provider

**⚠️ CONSTRAINT:** The LLM model chain is hard-locked.

**File:** `src/relate_voice/config.py` lines 54–58

```python
AUTHORISED_OPENROUTER_MODELS: list[str] = [
    "poolside/laguna-xs-2.1:free",
    "z-ai/glm-5.2:free",
    "cohere/north-mini-code:free",
]
```

This list is validated at config load time. If `voice-agent.yaml` references a
model not in this list, the application will refuse to start.

**To use a different model:**
1. Edit `config.py` — add your model to `AUTHORISED_OPENROUTER_MODELS`
2. Edit `config/voice-agent.yaml` — update `llm.models:` list
3. Redeploy

**To use a different LLM provider (not OpenRouter):**
1. Create `src/relate_voice/providers/your_provider.py`
2. Register in `registry.py`
3. Update `config/voice-agent.yaml` `llm:` section
4. Remove or modify the `AUTHORISED_OPENROUTER_MODELS` gate in `config.py`

**What breaks:** The fallback chain logic in `agent.py` assumes OpenRouter's
API format. A non-OpenAI-compatible provider needs a new adapter.

---

## Add Tools / MCP Integration

**Status: NOT IMPLEMENTED**

The tool system is planned but has zero code:

- `src/relate_voice/profiles/loader.py` has a `ProfileTools` schema (lines 49–51)
- The modularization plan references `ToolRegistry`, `ToolExecutor`, `McpConnector`
- None of these exist in the codebase

**When implemented, the integration point will be:**

```python
# src/relate_voice/agent.py — build_session()
session = AgentSession(
    # ... existing params ...
    tools=tool_registry.get_tools(),  # planned
)
```

**For now:** To add tool-like capability, you would need to:
1. Implement a tool executor
2. Wire it into `AgentSession` in `agent.py`
3. This requires modifying core agent code

---

## Change the Voice / TTS Voice

**File:** `config/voice-agent.yaml` line 17

```yaml
tts:
  voice: asteria
```

Deepgram aura-2 voices: `asteria`, `luna`, `stella`, `athena`, `hera`, `orion`,
`arcas`, `perseus`, `angus`, `canopus`. See Deepgram docs for current list.

**No code changes required.**

---

## Change the LLM Temperature / Token Limit

**File:** `config/voice-agent.yaml` lines 29–30

```yaml
llm:
  temperature: 0.4
  max_tokens: 300
```

**No code changes required.**

---

## Change the Turn Detection / Interruption Settings

**File:** `config/voice-agent.yaml` lines 36–47

```yaml
turn_handling:
  turn_detection: vad
  endpointing:
    min_delay_seconds: 0.5
    max_delay_seconds: 2.0
  interruption:
    enabled: true
    mode: vad
    min_duration_seconds: 0.3
    min_words: 0
    resume_false_interruption: true
    false_interruption_timeout_seconds: 1.5
```

- `min_delay_seconds` — how long silence before turn ends
- `max_delay_seconds` — maximum wait before forcing turn end
- `interruption.enabled` — allow barge-in
- `interruption.min_duration_seconds` — minimum speech to trigger interruption

**No code changes required.**

---

## Change the Rate Limiting

**File:** `config/voice-agent.yaml` lines 56–58

```yaml
ui:
  token_ttl_seconds: 120
  max_sessions_per_window: 10
  rate_window_seconds: 3600
```

- `max_sessions_per_window` — max sessions per origin per hour
- `rate_window_seconds` — rolling window duration

**No code changes required.**

---

## Change the Frontend UI

**Files:** `relate-voice-ui/` repository

- `index.html` — page structure
- `src/main.ts` — LiveKit client logic, state machine
- `assets/styles.css` — visual styling
- `build.mjs` — build configuration

**Key constant in `src/main.ts`:**

```typescript
const API_BASE = 'https://voice-api.relate-ai.site';
```

Change this if the backend domain changes.

**No backend changes required** for pure UI modifications.

---

## Add a New Provider (Any Type)

**Pattern:** Provider Registry

1. Create `src/relate_voice/providers/your_provider.py`
2. Implement a factory function:

```python
def build_your_provider(spec, environment):
    # spec = config section (e.g., config.stt)
    # environment = os.environ dict
    # Return a LiveKit-compatible provider instance
    ...
```

3. Register in `src/relate_voice/providers/registry.py`:

```python
from relate_voice.providers.your_provider import build_your_provider
registry.register("stt", "your_provider", build_your_provider)  # or "tts" or "llm"
```

4. Update `config/voice-agent.yaml` to reference your provider

**The registry is the single extension point.** No core code changes needed.

---

## Modify the Agent Dispatch Name

**File:** `config/voice-agent.yaml` line 49

```yaml
agent:
  dispatch_name: relate-voice-agent
```

This must match the `agent_name` in the LiveKit room configuration.
The gateway (`web.py`) dispatches agents with this name.

**What breaks:** If the dispatch name doesn't match, LiveKit won't route
rooms to the agent.

---

## Change the TURN Server Configuration

**File:** `docker-compose.yml` — coturn service and LiveKit config

```yaml
# coturn service
command:
  - "--static-auth-secret=${TURN_SECRET:-}"
  - "--allowed-peer-ip=10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"

# LiveKit config (inline in docker-compose.yml)
turn_servers:
  - host: turn.relate-ai.site
    port: 443
    protocol: tls
    secret: ${TURN_SECRET:-}
```

**What breaks:** If `TURN_SECRET` doesn't match between coturn and LiveKit,
TURN allocations will fail with 401 Unauthorized.

---

## Summary: What Requires Code Changes

| Modification | Code Change? | File |
|---|---|---|
| Persona/instructions | No | `config/voice-agent.yaml` |
| Greeting | No | `config/voice-agent.yaml` |
| TTS voice | No | `config/voice-agent.yaml` |
| STT/TTS provider | Yes (new file + registry) | `providers/`, `registry.py` |
| LLM model | Yes (`config.py` allowlist) | `config.py` |
| LLM provider | Yes (new file + registry + config gate) | `providers/`, `registry.py`, `config.py` |
| Tools/MCP | Yes (not yet implemented) | `agent.py` |
| Frontend UI | No (separate repo) | `relate-voice-ui/` |
| Rate limiting | No | `config/voice-agent.yaml` |
| Turn detection | No | `config/voice-agent.yaml` |
| Interruption | No | `config/voice-agent.yaml` |
