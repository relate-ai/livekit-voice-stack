"""Persistent Agent Store — portable, versioned agent configuration packages."""

from __future__ import annotations

import json
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0.0"
AGENT_ID_PATTERN = r"^[a-z][a-z0-9_-]*$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False)


class LLMProviderConfig(StrictModel):
    provider: str = Field(..., min_length=1, max_length=32)
    model: str = Field(..., min_length=1, max_length=128)
    temperature: float = Field(default=0.4, ge=0, le=2)
    max_tokens: int = Field(default=300, ge=32, le=4000)
    timeout_seconds: float = Field(default=20, gt=0, le=120)


class SpeechConfig(StrictModel):
    stt_provider: str = "deepgram"
    stt_model: str = "nova-3"
    stt_language: str = "en-US"
    tts_provider: str = "deepgram"
    tts_model: str = "aura-2"
    tts_voice: str = "asteria"
    tts_language: str = "en"


class TurnHandlingConfig(StrictModel):
    turn_detection: str = "turn_detector"
    endpointing_min_delay: float = 0.5
    endpointing_max_delay: float = 3.0
    interruption_enabled: bool = True
    interruption_mode: str = "vad"
    interruption_min_duration: float = 0.5
    preemptive_generation: bool = True
    user_turn_max_words: int | None = 200
    user_turn_max_duration: float | None = 60.0


class ToolAssignment(StrictModel):
    tool_id: str
    enabled: bool = True
    config: dict[str, str] = Field(default_factory=dict)


class AppearanceConfig(StrictModel):
    theme: str = "relate-prism"
    primary_color: str = "#E63946"
    accent_color: str = "#7B2FBE"
    background: str = "#FAFAFA"
    surface: str = "#FFFFFF"
    text_primary: str = "#1A1A2E"
    text_secondary: str = "#6B7280"


class AgentPackage(StrictModel):
    schema_version: str = SCHEMA_VERSION
    agent_id: str = Field(..., min_length=1, max_length=64, pattern=AGENT_ID_PATTERN)
    name: str = Field(..., min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    version: str = Field(default="1.0.0", min_length=1, max_length=16)
    created_at: str = ""
    updated_at: str = ""
    state: Literal["draft", "active"] = "draft"
    previous_version: str | None = None

    llm: LLMProviderConfig = LLMProviderConfig(provider="openrouter", model="poolside/laguna-xs-2.1:free")
    personality: str = "You are a warm, helpful voice assistant. Speak naturally and conversationally."
    greeting: str = "Hello! I'm your voice assistant. How can I help you today?"
    speech: SpeechConfig = SpeechConfig()
    turn_handling: TurnHandlingConfig = TurnHandlingConfig()
    tools: list[ToolAssignment] = Field(default_factory=list)
    appearance: AppearanceConfig = AppearanceConfig()
    credential_refs: list[str] = Field(default_factory=list)

    def touch(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        self.updated_at = now


class AgentStore:
    def __init__(self, base_path: str | Path) -> None:
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _agent_dir(self, agent_id: str) -> Path:
        return self.base_path / agent_id

    def _agent_file(self, agent_id: str) -> Path:
        return self._agent_dir(agent_id) / "agent.yaml"

    def _personality_file(self, agent_id: str) -> Path:
        return self._agent_dir(agent_id) / "personality.md"

    def list_agents(self) -> list[dict[str, str]]:
        agents = []
        for d in sorted(self.base_path.iterdir()):
            if d.is_dir() and (d / "agent.yaml").exists():
                try:
                    pkg = self.load_agent(d.name)
                    agents.append({
                        "agent_id": pkg.agent_id,
                        "name": pkg.name,
                        "version": pkg.version,
                        "state": pkg.state,
                        "description": pkg.description,
                        "llm_provider": pkg.llm.provider,
                        "llm_model": pkg.llm.model,
                        "updated_at": pkg.updated_at,
                    })
                except Exception:
                    continue
        return agents

    def load_agent(self, agent_id: str) -> AgentPackage:
        agent_file = self._agent_file(agent_id)
        if not agent_file.exists():
            raise FileNotFoundError(f"Agent not found: {agent_id}")
        raw = yaml.safe_load(agent_file.read_text(encoding="utf-8"))
        pkg = AgentPackage.model_validate(raw)
        personality_file = self._personality_file(agent_id)
        if personality_file.exists():
            pkg.personality = personality_file.read_text(encoding="utf-8").strip()
        return pkg

    def save_agent(self, pkg: AgentPackage, *, state: Literal["draft", "active"] | None = None) -> AgentPackage:
        pkg.touch()
        if state:
            pkg.state = state
        agent_dir = self._agent_dir(pkg.agent_id)
        agent_dir.mkdir(parents=True, exist_ok=True)
        # Save agent.yaml (without personality — that's separate)
        save_pkg = pkg.model_copy()
        save_data = save_pkg.model_dump()
        save_data.pop("personality", None)
        self._agent_file(pkg.agent_id).write_text(
            yaml.dump(save_data, default_flow_style=False, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        # Save personality.md
        self._personality_file(pkg.agent_id).write_text(
            pkg.personality + "\n",
            encoding="utf-8",
        )
        return pkg

    def delete_agent(self, agent_id: str) -> None:
        agent_dir = self._agent_dir(agent_id)
        if agent_dir.exists():
            shutil.rmtree(agent_dir)

    def duplicate_agent(self, source_id: str, new_id: str, new_name: str) -> AgentPackage:
        pkg = self.load_agent(source_id)
        pkg.agent_id = new_id
        pkg.name = new_name
        pkg.version = "1.0.0"
        pkg.state = "draft"
        pkg.created_at = ""
        pkg.previous_version = None
        return self.save_agent(pkg)

    def activate_agent(self, agent_id: str) -> AgentPackage:
        pkg = self.load_agent(agent_id)
        # Deactivate all others
        for d in self.base_path.iterdir():
            if d.is_dir() and (d / "agent.yaml").exists():
                try:
                    other = self.load_agent(d.name)
                    if other.state == "active" and other.agent_id != agent_id:
                        other.state = "draft"
                        self.save_agent(other)
                except Exception:
                    continue
        pkg.state = "active"
        return self.save_agent(pkg, state="active")

    def get_active_agent(self) -> AgentPackage | None:
        for d in self.base_path.iterdir():
            if d.is_dir() and (d / "agent.yaml").exists():
                try:
                    pkg = self.load_agent(d.name)
                    if pkg.state == "active":
                        return pkg
                except Exception:
                    continue
        return None

    def export_agent(self, agent_id: str) -> bytes:
        pkg = self.load_agent(agent_id)
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # agent.yaml (without secrets)
            save_data = pkg.model_dump()
            save_data.pop("personality", None)
            save_data["credential_refs"] = pkg.credential_refs
            zf.writestr(f"{agent_id}/agent.yaml", yaml.dump(save_data, default_flow_style=False, sort_keys=False, allow_unicode=True))
            zf.writestr(f"{agent_id}/personality.md", pkg.personality + "\n")
            zf.writestr(f"{agent_id}/appearance.yaml", yaml.dump(pkg.appearance.model_dump(), default_flow_style=False))
            zf.writestr(f"{agent_id}/tools.yaml", yaml.dump({"tools": [t.model_dump() for t in pkg.tools]}, default_flow_style=False))
            zf.writestr(f"{agent_id}/metadata.json", json.dumps({
                "schema_version": SCHEMA_VERSION,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "agent_id": agent_id,
                "version": pkg.version,
            }, indent=2))
        return buf.getvalue()

    def import_agent(self, data: bytes, *, override_id: str | None = None) -> AgentPackage:
        buf = BytesIO(data)
        with zipfile.ZipFile(buf, "r") as zf:
            # Security: check for path traversal
            for name in zf.namelist():
                if name.startswith("/") or ".." in name:
                    raise ValueError(f"Unsafe path in archive: {name}")

            # Find agent.yaml
            yaml_files = [n for n in zf.namelist() if n.endswith("/agent.yaml") or n == "agent.yaml"]
            if not yaml_files:
                raise ValueError("No agent.yaml found in archive")
            yaml_path = yaml_files[0]
            agent_dir_name = yaml_path.rsplit("/", 1)[0] if "/" in yaml_path else "."

            raw = yaml.safe_load(zf.read(yaml_path))
            pkg = AgentPackage.model_validate(raw)

            if override_id:
                pkg.agent_id = override_id

            # Load personality
            personality_path = f"{agent_dir_name}/personality.md"
            if personality_path in zf.namelist():
                pkg.personality = zf.read(personality_path).decode("utf-8").strip()

            # Load appearance
            appearance_path = f"{agent_dir_name}/appearance.yaml"
            if appearance_path in zf.namelist():
                pkg.appearance = AppearanceConfig.model_validate(yaml.safe_load(zf.read(appearance_path)))

            # Load tools
            tools_path = f"{agent_dir_name}/tools.yaml"
            if tools_path in zf.namelist():
                tools_data = yaml.safe_load(zf.read(tools_path))
                pkg.tools = [ToolAssignment.model_validate(t) for t in tools_data.get("tools", [])]

            pkg.state = "draft"
            pkg.version = "1.0.0"
            return self.save_agent(pkg)
