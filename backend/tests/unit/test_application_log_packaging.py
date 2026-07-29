"""XP-012 runtime logging packaging regression."""

from pathlib import Path


def test_backend_runtime_disables_uvicorn_access_logging():
    dockerfile = (Path(__file__).parents[2] / "Dockerfile").read_text(encoding="utf-8")

    assert '"--no-access-log"' in dockerfile
