"""Compose readiness-gating contract regressions."""

from pathlib import Path

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_backend_healthcheck_uses_ready_with_deliberate_bounds():
    compose = yaml.safe_load((REPOSITORY_ROOT / "docker-compose.dev.yml").read_text(encoding="utf-8"))
    healthcheck = compose["services"]["backend"]["healthcheck"]
    probe_command = " ".join(str(part) for part in healthcheck["test"])

    assert healthcheck["test"][:2] == ["CMD", "python"]
    assert "/ready" in probe_command
    assert "/health" not in probe_command
    assert "curl" not in probe_command
    assert healthcheck == {
        "test": healthcheck["test"],
        "interval": "2s",
        "timeout": "3s",
        "retries": 15,
        "start_period": "10s",
    }


def test_frontend_and_backend_depend_only_on_core_readiness():
    compose = yaml.safe_load((REPOSITORY_ROOT / "docker-compose.dev.yml").read_text(encoding="utf-8"))
    backend_dependencies = compose["services"]["backend"]["depends_on"]
    frontend_dependencies = compose["services"]["frontend"]["depends_on"]

    assert backend_dependencies == {
        "postgres-platform": {"condition": "service_healthy"},
        "redis": {"condition": "service_healthy"},
    }
    assert frontend_dependencies == {"backend": {"condition": "service_healthy"}}
