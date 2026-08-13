"""Disposable command-harness tests for scripts/dev-up.sh."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SOURCE_SCRIPT = REPOSITORY_ROOT / "scripts" / "dev-up.sh"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _run_disposable_dev_up(tmp_path: Path, mode: str | None, backend_health: str = "healthy"):
    workspace = tmp_path / "workspace"
    scripts_dir = workspace / "scripts"
    fake_bin = tmp_path / "bin"
    scripts_dir.mkdir(parents=True)
    fake_bin.mkdir()
    script = scripts_dir / "dev-up.sh"
    shutil.copy2(SOURCE_SCRIPT, script)
    script.chmod(0o755)
    (workspace / ".env").write_text(
        "PLATFORM_ENCRYPTION_KEY=test-key\nPROTECTED_CANARY=must-not-print\n",
        encoding="utf-8",
    )
    (workspace / "docker-compose.dev.yml").write_text("services: {}\n", encoding="utf-8")
    command_log = tmp_path / "commands.log"

    _write_executable(
        fake_bin / "docker",
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "$DEV_UP_COMMAND_LOG"
if [[ "$*" == *" ps "* ]]; then
  if [[ "$*" == *"--format json"* ]]; then
    if [[ "$DEV_UP_BACKEND_HEALTH" == "healthy" ]]; then
      printf '%s\n' '{"State":"running","Health":"healthy"}'
    else
      printf '%s\n' '{"State":"exited","Health":"starting"}'
    fi
  else
    printf '%s\n' "$DEV_UP_BACKEND_HEALTH"
  fi
fi
""",
    )
    _write_executable(fake_bin / "sleep", "#!/usr/bin/env bash\nexit 0\n")

    environment = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "DEV_UP_COMMAND_LOG": str(command_log),
        "DEV_UP_BACKEND_HEALTH": backend_health,
    }
    command = [str(script), *([mode] if mode else [])]
    completed = subprocess.run(
        command,
        cwd=workspace,
        env=environment,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    logged_commands = command_log.read_text(encoding="utf-8").splitlines()
    return completed, logged_commands


def _command_position(commands: list[str], fragment: str) -> int:
    return next(index for index, command in enumerate(commands) if fragment in command)


@pytest.mark.parametrize(
    ("mode", "build_fragment", "reset_fragment", "backend_fragment", "frontend_fragment"),
    [
        (
            None,
            "build backend",
            None,
            "up -d --force-recreate backend",
            "up -d --force-recreate frontend",
        ),
        (
            "--rebuild",
            "build --no-cache backend",
            None,
            "up -d --force-recreate backend",
            "up -d --force-recreate frontend",
        ),
        ("--reset", "build backend frontend", "down -v", "up -d backend", "up -d frontend"),
    ],
)
def test_dev_up_orders_migration_readiness_and_frontend(
    tmp_path,
    mode,
    build_fragment,
    reset_fragment,
    backend_fragment,
    frontend_fragment,
):
    completed, commands = _run_disposable_dev_up(tmp_path, mode)

    assert completed.returncode == 0, completed.stderr
    if reset_fragment is not None:
        assert _command_position(commands, reset_fragment) < _command_position(commands, build_fragment)
    positions = [
        _command_position(commands, build_fragment),
        _command_position(commands, "up -d --wait --wait-timeout 60 postgres-platform redis"),
        _command_position(commands, "stop frontend backend"),
        _command_position(commands, "run --rm --no-deps backend alembic upgrade head"),
        _command_position(commands, backend_fragment),
        _command_position(commands, "ps --format {{.Health}} backend"),
        _command_position(commands, frontend_fragment),
    ]
    assert positions == sorted(positions)


def test_dev_up_readiness_timeout_is_constant_and_nonzero(tmp_path):
    completed, _commands = _run_disposable_dev_up(tmp_path, None, backend_health="starting")
    combined_output = completed.stdout + completed.stderr

    assert completed.returncode != 0
    assert "[dev-up] backend readiness timed out" in combined_output
    assert "docker compose -f docker-compose.dev.yml logs backend" in combined_output
    assert "must-not-print" not in combined_output
