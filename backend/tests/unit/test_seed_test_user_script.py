"""Tests for backend/scripts/seed_test_user.py lifecycle hygiene."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPOSITORY_ROOT / "backend" / "scripts" / "seed_test_user.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("seed_test_user", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeSession:
    def __init__(self, existing):
        self._existing = existing
        self.added: list[object] = []
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def scalar(self, _stmt):
        return self._existing

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        obj.id = 1


class FakeEngine:
    def __init__(self):
        self.dispose_calls = 0

    async def dispose(self):
        self.dispose_calls += 1


@pytest.fixture()
def seed_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://platform:test@localhost/platform")
    monkeypatch.delenv("E2E_TEST_USERNAME", raising=False)
    monkeypatch.delenv("E2E_TEST_PASSWORD", raising=False)


def _install_fakes(monkeypatch, existing_user):
    module = _load_module()
    engine = FakeEngine()

    def fake_create_engine(_url, **_kwargs):
        return engine

    session = FakeSession(existing_user)
    fake_sessionmaker = lambda _engine, **_kwargs: lambda: session  # noqa: E731

    monkeypatch.setattr(module, "create_async_engine", fake_create_engine)
    monkeypatch.setattr(module, "async_sessionmaker", fake_sessionmaker)
    return module, engine


async def test_noop_existing_user_path_disposes_engine(monkeypatch, seed_env, capsys):
    existing = SimpleNamespace(id=42, username="e2e_user")
    module, engine = _install_fakes(monkeypatch, existing)

    await module.main()

    assert engine.dispose_calls == 1
    assert "already exists" in capsys.readouterr().out


async def test_create_user_path_disposes_engine(monkeypatch, seed_env, capsys):
    module, engine = _install_fakes(monkeypatch, None)

    await module.main()

    assert engine.dispose_calls == 1
    out = capsys.readouterr().out
    assert "Created user e2e_user" in out
    assert "e2e_password_123" not in out
