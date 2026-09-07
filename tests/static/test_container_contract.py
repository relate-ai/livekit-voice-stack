from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_python_services_create_the_agent_store_before_dropping_privileges():
    for filename in ("Dockerfile.agent", "Dockerfile.api"):
        dockerfile = (ROOT / filename).read_text()

        create_position = dockerfile.find("install -d -o app -g app /app/agents")
        user_position = dockerfile.find("USER 10001")
        assert create_position >= 0, filename
        assert create_position < user_position, filename
