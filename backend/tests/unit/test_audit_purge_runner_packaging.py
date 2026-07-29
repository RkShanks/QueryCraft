"""Container packaging regression for the documented audit purge runner."""

from pathlib import Path


def test_backend_runtime_image_packages_documented_runner():
    backend_root = Path(__file__).parents[2]
    dockerfile = (backend_root / "Dockerfile").read_text(encoding="utf-8")

    assert "COPY --chown=app:app scripts/ ./scripts/" in dockerfile
