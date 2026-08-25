"""Disposable command-harness tests for scripts/restore-mssql.sh."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SOURCE_SCRIPT = REPOSITORY_ROOT / "scripts" / "restore-mssql.sh"

FAKE_DOCKER = r"""#!/usr/bin/env bash
set -uo pipefail
args="$*"
if [[ "$args" != *"mssql-source"* ]]; then
  exit 0
fi

# Health probe: -Q "SELECT 1"
if [[ "$args" == *'-Q'* ]]; then
  exit "${RESTORE_HEALTH_EXIT:-0}"
fi

# Everything else consumes a batch on stdin.
input=$(cat)
printf '%s\n' "$input" >> "$RESTORE_SQL_LOG"
printf '\n===BATCH===\n' >> "$RESTORE_SQL_LOG"

if [[ "$input" == *"THEN N'ABSENT'"* ]] || [[ "$input" == *"THEN N'ONLINE'"* ]]; then
  printf '%s\n' "${RESTORE_DB_STATE_RESPONSE:-ABSENT}"
  exit 0
fi

if [[ "$input" == *"DROP DATABASE"* ]]; then
  echo "DROP" >> "$RESTORE_ACTIONS"
fi

if [[ "$input" == *"RESTORE DATABASE"* ]]; then
  echo "RESTORE" >> "$RESTORE_ACTIONS"
  if [[ "${RESTORE_RESTORE_RESULT:-ok}" == "fail" ]]; then
    exit 1
  fi
fi

exit 0
"""


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


class RestoreWorkspace:
    def __init__(self, tmp_path: Path):
        self.workspace = tmp_path / "workspace"
        self.scripts_dir = self.workspace / "scripts"
        self.fake_bin = tmp_path / "bin"
        self.scripts_dir.mkdir(parents=True)
        self.fake_bin.mkdir()
        self.script = self.scripts_dir / "restore-mssql.sh"
        shutil.copy2(SOURCE_SCRIPT, self.script)
        self.script.chmod(0o755)
        _write_executable(self.fake_bin / "docker", FAKE_DOCKER)

        (self.workspace / "docker-compose.dev.yml").write_text("services: {}\n", encoding="utf-8")
        self.sql_log = tmp_path / "sql.log"
        self.actions_log = tmp_path / "actions.log"

    def write_env(self, lines: list[str]) -> None:
        (self.workspace / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def run(self, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
        environment = {
            **os.environ,
            "PATH": f"{self.fake_bin}:{os.environ['PATH']}",
            "RESTORE_SQL_LOG": str(self.sql_log),
            "RESTORE_ACTIONS": str(self.actions_log),
            "RESTORE_WAIT_ATTEMPTS": "2",
        }
        environment.pop("MSSQL_USER", None)
        environment.pop("MSSQL_PASSWORD", None)
        environment.pop("MSSQL_SA_PASSWORD", None)
        if extra_env:
            environment.update(extra_env)
        return subprocess.run(
            [str(self.script)],
            cwd=self.workspace,
            env=environment,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )

    @property
    def sql_batches(self) -> list[str]:
        if not self.sql_log.exists():
            return []
        raw = self.sql_log.read_text(encoding="utf-8")
        return [batch.strip("\n") for batch in raw.replace("===BATCH===", "\x00").split("\x00") if batch.strip()]

    @property
    def actions(self) -> list[str]:
        if not self.actions_log.exists():
            return []
        return [line for line in self.actions_log.read_text(encoding="utf-8").splitlines() if line]


@pytest.fixture()
def ws(tmp_path: Path) -> RestoreWorkspace:
    return RestoreWorkspace(tmp_path)


SAFE_ENV = {
    "MSSQL_SA_PASSWORD": "sa-canary-password",
    "MSSQL_USER": "adventureworks_user",
    "MSSQL_PASSWORD": "app-canary-password",
}


def test_hostile_user_value_rejected_before_any_sql(ws):
    completed = ws.run(
        extra_env={
            **SAFE_ENV,
            "MSSQL_USER": "user']; DROP DATABASE master;--",
        }
    )

    assert completed.returncode != 0
    assert "unsafe" in completed.stderr.lower()
    assert ws.sql_batches == []
    assert ws.actions == []
    assert "DROP DATABASE master" not in (completed.stdout + completed.stderr)


def test_control_character_in_password_rejected_before_any_sql(ws):
    completed = ws.run(
        extra_env={
            **SAFE_ENV,
            "MSSQL_PASSWORD": "pass\nword",
        }
    )

    assert completed.returncode != 0
    assert ws.sql_batches == []


def test_hostile_user_from_env_file_rejected(ws):
    ws.write_env(["MSSQL_USER=user]name", "MSSQL_PASSWORD=app-canary-password", "MSSQL_SA_PASSWORD=sa-canary-password"])

    completed = ws.run()

    assert completed.returncode != 0
    assert ws.sql_batches == []


def test_single_quote_in_password_is_escaped_not_executed(ws):
    completed = ws.run(extra_env={**SAFE_ENV, "MSSQL_PASSWORD": "can'ary"})

    assert completed.returncode == 0, completed.stderr
    login_batches = [batch for batch in ws.sql_batches if "CREATE LOGIN" in batch]
    assert len(login_batches) == 1
    assert "N'can''ary'" in login_batches[0]
    assert "N'can'ary'" not in login_batches[0]


def test_unhealthy_container_times_out_with_constant_sanitized_message(ws):
    completed = ws.run(extra_env={**SAFE_ENV, "RESTORE_HEALTH_EXIT": "1"})

    assert completed.returncode != 0
    combined = completed.stdout + completed.stderr
    assert "timed out" in combined.lower()
    assert "sa-canary-password" not in combined
    assert "app-canary-password" not in combined


def test_absent_database_restored_exactly_once_without_drop(ws):
    completed = ws.run(extra_env={**SAFE_ENV, "RESTORE_DB_STATE_RESPONSE": "ABSENT"})

    assert completed.returncode == 0, completed.stderr
    assert ws.actions.count("RESTORE") == 1
    assert "DROP" not in ws.actions


def test_partial_restore_state_recovers_via_drop_then_restore(ws):
    completed = ws.run(extra_env={**SAFE_ENV, "RESTORE_DB_STATE_RESPONSE": "RECOVERING"})

    assert completed.returncode == 0, completed.stderr
    assert ws.actions == ["DROP", "RESTORE"]


def test_online_database_rerun_is_idempotent_and_still_configures_role(ws):
    completed = ws.run(extra_env={**SAFE_ENV, "RESTORE_DB_STATE_RESPONSE": "ONLINE"})

    assert completed.returncode == 0, completed.stderr
    assert ws.actions == []
    role_batches = [batch for batch in ws.sql_batches if "db_datareader" in batch]
    assert len(role_batches) == 1
    assert "[adventureworks_user]" in role_batches[0]


def test_failed_restore_aborts_before_login_configuration(ws):
    completed = ws.run(
        extra_env={
            **SAFE_ENV,
            "RESTORE_DB_STATE_RESPONSE": "ABSENT",
            "RESTORE_RESTORE_RESULT": "fail",
        }
    )

    assert completed.returncode != 0
    assert "restore failed" in (completed.stdout + completed.stderr).lower()
    assert all("CREATE LOGIN" not in batch for batch in ws.sql_batches)


def test_diagnostics_never_contain_secret_values(ws):
    completed = ws.run(extra_env={**SAFE_ENV})

    combined = completed.stdout + completed.stderr
    assert completed.returncode == 0, completed.stderr
    assert "sa-canary-password" not in combined
    assert "app-canary-password" not in combined
