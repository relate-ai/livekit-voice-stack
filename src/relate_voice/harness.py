"""In-network scripted voice-conversation harness (temporary validation service)."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import math
import os
import re
import struct
import time
import urllib.request
import uuid
import wave
from typing import Any, cast

from livekit import api, rtc
from livekit.protocol import models

RATE = 24000
CHANNELS = 1
FRAME_SAMPLES = 480
FRAME_BYTES = FRAME_SAMPLES * 2
RMS_THRESHOLD = 500.0
logger = logging.getLogger("relate_voice.harness")
SILENCE_END_FRAMES = 100
GRACE_SECONDS = 180

PROBES = {
    "remember": "Hello assistant. Please remember the code word blueberry.",
    "recall": "What was the code word I asked you to remember?",
    "count": "Please count slowly from one to thirty, saying one number at a time.",
    "interrupt": "Stop counting. What is two plus two?",
}


def normalize_text(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower())


def fuzzy_contains(haystack: str, needle: str) -> bool:
    hay, want = normalize_text(haystack), normalize_text(needle)
    return bool(want) and want in hay


def frame_rms(data: bytes) -> float:
    if not data or not data.strip(b"\x00"):
        return 0.0
    count = len(data) // 2
    samples = struct.unpack(f"<{count}h", data[: count * 2])
    return math.sqrt(sum(s * s for s in samples) / count)


def speech_active(rms: float, threshold: float = RMS_THRESHOLD) -> bool:
    return rms >= threshold


def find_speech_end(active: list[bool], start: int, min_silence: int) -> int | None:
    quiet = 0
    for i in range(start, len(active)):
        if active[i]:
            quiet = 0
        else:
            quiet += 1
            if quiet >= min_silence:
                return i + 1
    return None


def deepgram_tts(api_key: str, text: str) -> bytes:
    request = urllib.request.Request(
        "https://api.deepgram.com/v1/speak?model=aura-2-asteria-en&encoding=linear16&sample_rate=24000",
        data=json.dumps({"text": text}).encode(),
        headers={"Authorization": f"Token {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
        return bytes(response.read())


def deepgram_transcribe(api_key: str, pcm: bytes) -> str:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        wav.writeframes(pcm)
    request = urllib.request.Request(
        "https://api.deepgram.com/v1/listen?model=nova-3&language=en-US&smart_format=true",
        data=buffer.getvalue(),
        headers={"Authorization": f"Token {api_key}", "Content-Type": "audio/wav"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
        payload = json.loads(response.read().decode())
    alternatives = payload["results"]["channels"][0]["alternatives"]
    return alternatives[0]["transcript"] if alternatives else ""


def api_base(livekit_url: str) -> str:
    return livekit_url.replace("ws://", "http://").replace("wss://", "https://")


def mint_token(key: str, secret: str, room: str, identity: str) -> str:
    return (
        api.AccessToken(key, secret)
        .with_identity(identity)
        .with_grants(api.VideoGrants(room_join=True, room=room))
        .with_room_config(
            api.RoomConfiguration(agents=[api.RoomAgentDispatch(agent_name="relate-voice-agent")])
        )
        .to_jwt()
    )


class Conversation:
    def __init__(self, room: rtc.Room) -> None:
        self.room = room
        self.frames: list[tuple[float, bytes]] = []
        self.track_ready = asyncio.Event()

    async def publish_wav(self, pcm: bytes) -> None:
        source = rtc.AudioSource(RATE, CHANNELS)
        track = rtc.LocalAudioTrack.create_audio_track("harness-mic", source)
        await self.room.local_participant.publish_track(
            track, rtc.TrackPublishOptions(source=cast(Any, models.TrackSource.Value("MICROPHONE")))
        )
        await self._pump(source, b"\x00" * FRAME_BYTES * 15 + pcm + b"\x00" * FRAME_BYTES * 40)

    async def _pump(self, source: rtc.AudioSource, pcm: bytes) -> None:
        for offset in range(0, len(pcm), FRAME_BYTES):
            chunk = pcm[offset : offset + FRAME_BYTES]
            if len(chunk) < FRAME_BYTES:
                chunk = chunk + b"\x00" * (FRAME_BYTES - len(chunk))
            await source.capture_frame(rtc.AudioFrame(chunk, RATE, CHANNELS, FRAME_SAMPLES))
            await asyncio.sleep(FRAME_BYTES / (RATE * 2))

    async def next_segment(self, timeout: float) -> dict[str, Any]:
        start = time.monotonic()
        begin: float | None = None
        collected: list[bytes] = []
        quiet = 0
        base = len(self.frames)
        while time.monotonic() - start < timeout:
            await asyncio.sleep(0.05)
            fresh = self.frames[base:]
            base = len(self.frames)
            for stamp, data in fresh:
                active = speech_active(frame_rms(data))
                if begin is None:
                    if active:
                        begin = stamp
                        collected.append(data)
                        quiet = 0
                else:
                    collected.append(data)
                    quiet = 0 if active else quiet + 1
                    if quiet >= SILENCE_END_FRAMES and len(collected) > 50:
                        return {"pcm": b"".join(collected), "started_at": begin, "ended_at": stamp}
        if begin is not None and len(collected) > 50:
            last = self.frames[-1][0] if self.frames else start
            return {"pcm": b"".join(collected), "started_at": begin, "ended_at": last}
        raise TimeoutError("no agent speech observed")


async def run() -> dict[str, Any]:
    env = os.environ
    for name in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", "DEEPGRAM_API_KEY"):
        if not env.get(name):
            return {"passed": False, "error": f"missing {name}", "turns": []}
    stamp = uuid.uuid4().hex[:8]
    room_name = f"voice-harness-{stamp}"
    verdict: dict[str, Any] = {"passed": False, "room": room_name, "turns": [], "error": None}
    room = rtc.Room()
    try:
        probes = {name: deepgram_tts(env["DEEPGRAM_API_KEY"], text) for name, text in PROBES.items()}
    except Exception as exc:
        verdict["error"] = f"probe synthesis failed: {type(exc).__name__}"
        return verdict
    conv = Conversation(room)

    @room.on("track_subscribed")
    def on_track(track: rtc.Track, *_args: Any) -> None:
        if track.kind != rtc.TrackKind.KIND_AUDIO:
            return

        async def read_stream() -> None:
            try:
                async for event in rtc.AudioStream(track, sample_rate=RATE, num_channels=CHANNELS):
                    conv.frames.append((time.monotonic(), bytes(event.frame.data)))
            except Exception as exc:
                logger.debug("audio stream ended: %s", type(exc).__name__)

        asyncio.ensure_future(read_stream())

    try:
        token = mint_token(env["LIVEKIT_API_KEY"], env["LIVEKIT_API_SECRET"], room_name, f"harness-{stamp}")
        await room.connect(env["LIVEKIT_URL"], token)
        greeting = await conv.next_segment(timeout=90)
        greeting_text = deepgram_transcribe(env["DEEPGRAM_API_KEY"], greeting["pcm"])
        verdict["turns"].append(
            {"user": None, "agent": greeting_text, "agent_frames": len(greeting["pcm"]) // FRAME_BYTES}
        )
        if not fuzzy_contains(greeting_text, "help"):
            verdict["error"] = f"greeting did not offer help: {greeting_text[:120]}"
            return verdict
        try:
            lk_url = api_base(env["LIVEKIT_URL"])
            async with api.LiveKitAPI(lk_url, env["LIVEKIT_API_KEY"], env["LIVEKIT_API_SECRET"]) as lk:
                parts = await lk.room.list_participants(api.ListParticipantsRequest(room=room_name))
                for participant in parts.participants:
                    if participant.identity.startswith("agent-"):
                        verdict["agent_model"] = participant.attributes.get("relate_active_llm_model")
                        verdict["agent_provider"] = participant.attributes.get("relate_active_llm_provider")
        except Exception as exc:
            verdict["error"] = f"model attribution read failed: {type(exc).__name__}"
            return verdict
        await conv.publish_wav(probes["remember"])
        answer1 = await conv.next_segment(timeout=90)
        answer1_text = deepgram_transcribe(env["DEEPGRAM_API_KEY"], answer1["pcm"])
        verdict["turns"].append({"user": PROBES["remember"], "agent": answer1_text})
        await conv.publish_wav(probes["recall"])
        answer2 = await conv.next_segment(timeout=90)
        answer2_text = deepgram_transcribe(env["DEEPGRAM_API_KEY"], answer2["pcm"])
        verdict["turns"].append({"user": PROBES["recall"], "agent": answer2_text})
        if not fuzzy_contains(answer2_text, "blueberry"):
            verdict["error"] = f"recall answer missed code word: {answer2_text[:160]}"
            return verdict
        count_task = asyncio.ensure_future(conv.publish_wav(probes["count"]))
        await asyncio.sleep(1)
        active_seen = False
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            await asyncio.sleep(0.1)
            recent = [speech_active(frame_rms(data)) for _, data in conv.frames[-150:]]
            if sum(recent) > 60:
                active_seen = True
                break
        if not active_seen:
            count_task.cancel()
            verdict["error"] = "agent never started counting"
            return verdict
        interrupt_at = time.monotonic()
        overlap = any(speech_active(frame_rms(data)) for _, data in conv.frames[-25:])
        await conv.publish_wav(probes["interrupt"])
        count_task.cancel()
        quiet_start: float | None = None
        yielded_ms: int | None = None
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            await asyncio.sleep(0.1)
            recent = [speech_active(frame_rms(data)) for _, data in conv.frames[-15:]]
            if all(not active for active in recent):
                if quiet_start is None:
                    quiet_start = time.monotonic()
                elif (time.monotonic() - quiet_start) * 1000 >= 1200:
                    yielded_ms = int((quiet_start - interrupt_at) * 1000)
                    break
            else:
                quiet_start = None
        answer3 = await conv.next_segment(timeout=90)
        answer3_text = deepgram_transcribe(env["DEEPGRAM_API_KEY"], answer3["pcm"])
        verdict["turns"].append({"user": PROBES["interrupt"], "agent": answer3_text})
        verdict["barge_in"] = {"overlap_proven": overlap, "yield_ms": yielded_ms}
        if yielded_ms is None:
            verdict["error"] = "agent did not yield to interruption"
            return verdict
        if not (fuzzy_contains(answer3_text, "four") or fuzzy_contains(answer3_text, "4")):
            verdict["error"] = f"math answer incorrect: {answer3_text[:160]}"
            return verdict
        verdict["passed"] = len(verdict["turns"]) >= 3
        return verdict
    except TimeoutError as exc:
        verdict["error"] = f"conversation timeout: {exc}"
        return verdict
    except Exception as exc:
        verdict["error"] = f"harness failure: {type(exc).__name__}: {exc}"
        return verdict


async def main() -> dict[str, Any]:
    verdict = await run()
    payload = json.dumps(verdict, separators=(",", ":"))
    print(f"HARNESS_RESULT {payload}", flush=True)
    try:
        room_name = verdict.get("room", "")
        env = os.environ
        lk_url = api_base(env["LIVEKIT_URL"])
        async with api.LiveKitAPI(lk_url, env["LIVEKIT_API_KEY"], env["LIVEKIT_API_SECRET"]) as lk:
            parts = await lk.room.list_participants(api.ListParticipantsRequest(room=room_name))
            for participant in parts.participants:
                if participant.identity.startswith("harness-"):
                    chunks = [payload[i : i + 2800] for i in range(0, len(payload), 2800)]
                    for index, chunk in enumerate(chunks):
                        await lk.room.update_participant(
                            api.UpdateParticipantRequest(
                                room=room_name,
                                identity=participant.identity,
                                attributes={f"relate_harness_{index}": chunk},
                            )
                        )
                    await lk.room.update_participant(
                        api.UpdateParticipantRequest(
                            room=room_name,
                            identity=participant.identity,
                            attributes={
                                "relate_harness_chunks": str(len(chunks)),
                                "relate_harness_done": "true",
                            },
                        )
                    )
    except Exception as exc:
        print(f"ATTRIBUTION_FAILED {type(exc).__name__}", flush=True)
    await asyncio.sleep(GRACE_SECONDS)
    return verdict


if __name__ == "__main__":
    import sys as _sys

    final = asyncio.run(main())
    _sys.exit(0 if final.get("passed") else 1)
