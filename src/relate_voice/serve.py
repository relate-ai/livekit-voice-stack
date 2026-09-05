from __future__ import annotations

import os
from pathlib import Path

import uvicorn

from relate_voice.config import load_config
from relate_voice.web import create_app

config = load_config(Path(os.environ.get("VOICE_CONFIG_PATH", "/app/config/voice-agent.yaml")))
app = create_app(config, os.environ, Path(os.environ.get("WEB_STATIC_PATH", "/app/web")))


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=False)  # noqa: S104


if __name__ == "__main__":
    main()
