"""Disposable command-harness tests for scripts/setup-source-dbs.sh."""

import io
import os
import shutil
import signal
import subprocess
import tarfile
import time
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SOURCE_SCRIPT = REPOSITORY_ROOT / "scripts" / "setup-source-dbs.sh"

SCHEMA_BYTES = b"-- sakila schema\nCREATE TABLE film (film_id INT);\n"
DATA_BYTES = b"-- sakila data\nINSERT INTO film VALUES (1);\n"


def _make_sakila_tar(path: Path, schema: bytes = SCHEMA_BYTES, data: bytes = DATA_BYTES) -> None:
    with tarfile.open(path, "w:gz") as archive:
        for member_name, payload in (
            ("sakila-db/sakila-schema.sql", schema),
            ("sakila-db/sakila-data.sql", data),
        ):
            info = tarfile.TarInfo(member_name)
            info.size = len(payload)
            info.mtime = int(time.time())
            archive.addfile(info, io.BytesIO(payload))


def _sha256_of(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


FAKE_CURL = """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "$SETUP_COMMAND_LOG"
out=""
prev=""
for arg in "$@"; do
  if [[ "$prev" == "-o" ]]; then out="$arg"; fi
  prev="$arg"
done
url="${@: -1}"
case "$url" in
  *sakila*) key="SAKILA" ;;
  *AdventureWorksLT2022.bak*) key="AWLT" ;;
  *) key="UNKNOWN" ;;
esac
sleep "${SETUP_CURL_SLEEP:-0}"
src_var="SETUP_FIXTURE_FILE_${key}"
if [[ -n "${!src_var:-}" ]]; then
  cp "${!src_var}" "$out"
fi
exit "${SETUP_CURL_EXIT:-0}"
"""


class SetupWorkspace:
    def __init__(self, tmp_path: Path):
        self.workspace = tmp_path / "workspace"
        self.scripts_dir = self.workspace / "scripts"
        self.fake_bin = tmp_path / "bin"
        self.tmp_scratch = tmp_path / "tmpscratch"
        self.command_log = tmp_path / "commands.log"
        self.checksums_file = self.scripts_dir / "fixtures.sha256"

        self.scripts_dir.mkdir(parents=True)
        self.fake_bin.mkdir()
        self.tmp_scratch.mkdir()
        self.script = self.scripts_dir / "setup-source-dbs.sh"
        shutil.copy2(SOURCE_SCRIPT, self.script)
        self.script.chmod(0o755)
        _write_executable(self.fake_bin / "curl", FAKE_CURL)

        self.fixtures_dir = tmp_path / "served"
        self.fixtures_dir.mkdir()
        self.sakila_fixture: Path | None = None
        self.awlt_fixture: Path | None = None

    def serve_sakila_from(self, path: Path) -> None:
        self.sakila_fixture = path

    def serve_awlt_from(self, path: Path) -> None:
        self.awlt_fixture = path

    def write_checksums(self, entries: dict[str, str]) -> None:
        lines = [f"{digest}  {name}" for name, digest in sorted(entries.items())]
        self.checksums_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def run(
        self, extra_env: dict[str, str] | None = None, sigterm_after: str | None = None
    ) -> subprocess.CompletedProcess:
        environment = {
            **os.environ,
            "PATH": f"{self.fake_bin}:{os.environ['PATH']}",
            "TMPDIR": str(self.tmp_scratch),
            "SETUP_COMMAND_LOG": str(self.command_log),
        }
        if self.sakila_fixture is not None:
            environment["SETUP_FIXTURE_FILE_SAKILA"] = str(self.sakila_fixture)
        if self.awlt_fixture is not None:
            environment["SETUP_FIXTURE_FILE_AWLT"] = str(self.awlt_fixture)
        if extra_env:
            environment.update(extra_env)

        if sigterm_after is None:
            return subprocess.run(
                [str(self.script)],
                cwd=self.workspace,
                env=environment,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )

        process = subprocess.Popen(
            [str(self.script)],
            cwd=self.workspace,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if self.command_log.exists() and self.command_log.read_text(encoding="utf-8").strip():
                break
            if process.poll() is not None:
                break
            time.sleep(0.05)
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=20)
        except subprocess.TimeoutExpired as exc:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            raise AssertionError("script did not exit within 20s of SIGTERM") from exc
        return subprocess.CompletedProcess([str(self.script)], process.returncode, stdout=stdout, stderr=stderr)

    @property
    def commands(self) -> list[str]:
        if not self.command_log.exists():
            return []
        return self.command_log.read_text(encoding="utf-8").splitlines()

    def scratch_entries(self) -> list[str]:
        return sorted(entry.name for entry in self.tmp_scratch.iterdir())

    def installed_files(self) -> set[str]:
        db_test = self.workspace / "dbTest"
        if not db_test.exists():
            return set()
        return {str(path.relative_to(db_test)) for path in db_test.rglob("*") if path.is_file()}


@pytest.fixture()
def ws(tmp_path: Path) -> SetupWorkspace:
    return SetupWorkspace(tmp_path)


def _happy_fixtures(ws: SetupWorkspace) -> tuple[Path, Path]:
    sakila_archive = ws.fixtures_dir / "sakila-db.tar.gz"
    awlt_backup = ws.fixtures_dir / "AdventureWorksLT2022.bak"
    _make_sakila_tar(sakila_archive)
    awlt_backup.write_bytes(b"RESTORE-BACKUP-IMAGE\n")
    ws.serve_sakila_from(sakila_archive)
    ws.serve_awlt_from(awlt_backup)
    ws.write_checksums(
        {
            "sakila-db.tar.gz": _sha256_of(sakila_archive),
            "AdventureWorksLT2022.bak": _sha256_of(awlt_backup),
        }
    )
    return sakila_archive, awlt_backup


def test_missing_checksum_file_fails_closed_before_any_download(ws):
    completed = ws.run()

    assert completed.returncode != 0
    assert "checksum" in completed.stderr.lower()
    assert ws.commands == []
    assert ws.installed_files() == set()
    assert ws.scratch_entries() == []


def test_missing_checksum_entry_fails_before_download_of_other_fixture(ws):
    awlt_backup = ws.fixtures_dir / "AdventureWorksLT2022.bak"
    awlt_backup.write_bytes(b"RESTORE-BACKUP-IMAGE\n")
    ws.serve_awlt_from(awlt_backup)
    ws.write_checksums({"AdventureWorksLT2022.bak": _sha256_of(awlt_backup)})

    completed = ws.run()

    assert completed.returncode != 0
    assert "sakila" in completed.stderr.lower()
    assert ws.commands == []


def test_failed_download_exits_nonzero_without_artifacts_or_temp_leftovers(ws):
    _, awlt_backup = _happy_fixtures(ws)

    completed = ws.run(extra_env={"SETUP_CURL_EXIT": "22"})

    assert completed.returncode != 0
    assert "download failed" in completed.stderr.lower()
    assert ws.installed_files() == set()
    assert ws.scratch_entries() == []


def test_corrupt_archive_rejected_without_install_and_temp_cleaned(ws):
    corrupt_payload = b"this is not a gzip archive\n"
    corrupt_file = ws.fixtures_dir / "corrupt.tar.gz"
    corrupt_file.write_bytes(corrupt_payload)
    awlt_backup = ws.fixtures_dir / "AdventureWorksLT2022.bak"
    awlt_backup.write_bytes(b"RESTORE-BACKUP-IMAGE\n")
    ws.serve_sakila_from(corrupt_file)
    ws.serve_awlt_from(awlt_backup)
    ws.write_checksums(
        {
            "sakila-db.tar.gz": _sha256_of(corrupt_file),
            "AdventureWorksLT2022.bak": _sha256_of(awlt_backup),
        }
    )

    completed = ws.run()

    assert completed.returncode != 0
    assert ws.installed_files() == set()
    assert ws.scratch_entries() == []


def test_checksum_mismatch_rejected_before_extraction_or_install(ws):
    sakila_archive = ws.fixtures_dir / "sakila-db.tar.gz"
    _make_sakila_tar(sakila_archive)
    other_archive = ws.fixtures_dir / "other.tar.gz"
    _make_sakila_tar(other_archive, schema=b"-- different content\n")
    awlt_backup = ws.fixtures_dir / "AdventureWorksLT2022.bak"
    awlt_backup.write_bytes(b"RESTORE-BACKUP-IMAGE\n")
    ws.serve_sakila_from(sakila_archive)
    ws.serve_awlt_from(awlt_backup)
    ws.write_checksums(
        {
            "sakila-db.tar.gz": _sha256_of(other_archive),
            "AdventureWorksLT2022.bak": _sha256_of(awlt_backup),
        }
    )
    scratch_before = ws.scratch_entries()

    completed = ws.run()

    assert completed.returncode != 0
    combined = (completed.stdout + completed.stderr).lower()
    assert "checksum mismatch" in combined
    assert ws.installed_files() == set()
    assert ws.scratch_entries() == scratch_before


def test_interrupted_run_leaves_no_installed_files_and_no_temp_leftovers(ws):
    _happy_fixtures(ws)

    completed = ws.run(
        extra_env={"SETUP_CURL_SLEEP": "5"},
        sigterm_after="first-invocation",
    )

    assert completed.returncode != 0
    assert ws.installed_files() == set()
    assert ws.scratch_entries() == []


def test_rerun_after_failed_download_completes(ws):
    _happy_fixtures(ws)

    failed = ws.run(extra_env={"SETUP_CURL_EXIT": "22"})
    assert failed.returncode != 0

    succeeded = ws.run()
    assert succeeded.returncode == 0, succeeded.stderr
    assert {
        "mysql/init/01-schema.sql",
        "mysql/init/02-data.sql",
        "mssql/backup/AdventureWorksLT2022.bak",
        "mysql/init/03-grants.sql",
    } <= ws.installed_files()


def test_rerun_after_interrupted_install_recovers(ws):
    _happy_fixtures(ws)
    db_test = ws.workspace / "dbTest"
    (db_test / "mysql" / "init").mkdir(parents=True)
    (db_test / "mysql" / "init" / "01-schema.sql").write_bytes(SCHEMA_BYTES[:5])

    completed = ws.run()

    assert completed.returncode == 0, completed.stderr
    assert {
        "mysql/init/01-schema.sql",
        "mysql/init/02-data.sql",
        "mssql/backup/AdventureWorksLT2022.bak",
        "mysql/init/03-grants.sql",
    } <= ws.installed_files()


def test_second_successful_run_is_idempotent_and_skips_downloads(ws):
    _happy_fixtures(ws)

    first = ws.run()
    assert first.returncode == 0, first.stderr
    commands_after_first = len(ws.commands)

    second = ws.run()
    assert second.returncode == 0, second.stderr
    assert len(ws.commands) == commands_after_first


def test_downloads_are_https_only_with_fail_aware_curl_flags(ws):
    _happy_fixtures(ws)

    completed = ws.run()

    assert completed.returncode == 0, completed.stderr
    assert len(ws.commands) == 2
    for invocation in ws.commands:
        parts = invocation.split()
        assert "--proto" in parts
        assert "=https" in parts
        assert any(part.startswith("-f") for part in parts)
        url = parts[-1]
        assert url.startswith("https://")


def test_success_output_is_sanitized_and_installs_expected_files(ws):
    secret_canary = "SUPERSECRET-CANARY-value"
    sakila_archive, awlt_backup = _happy_fixtures(ws)
    payload_canary = b"CANARY-IN-FIXTURE-PAYLOAD"

    completed = ws.run(extra_env={"PROTECTED_CANARY": secret_canary})

    assert completed.returncode == 0, completed.stderr
    combined = completed.stdout + completed.stderr
    assert secret_canary not in combined
    assert payload_canary.decode() not in combined
    grants = (ws.workspace / "dbTest" / "mysql" / "init" / "03-grants.sql").read_text(encoding="utf-8")
    assert "GRANT SELECT ON sakila.*" in grants
    assert (
        (ws.workspace / "dbTest" / "mssql" / "backup" / "AdventureWorksLT2022.bak")
        .read_bytes()
        .startswith(b"RESTORE-BACKUP-IMAGE")
    )
