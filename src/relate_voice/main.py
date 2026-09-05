from __future__ import annotations

import logging
import os
from pathlib import Path

from livekit import agents

from relate_voice.agent import build_server
from relate_voice.config import load_config, validate_agent_secret_references


def main() -> None:
    config = load_config(Path(os.environ.get("VOICE_CONFIG_PATH", "/app/config/voice-agent.yaml")))
    validate_agent_secret_references(config, os.environ)
    logging.basicConfig(
        level=config.observability.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    agents.cli.run_app(build_server(config, os.environ))


if __name__ == "__main__":
    main()
