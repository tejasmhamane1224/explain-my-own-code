"""Tests for emc quiz --dry-run command behavior and secret redaction output."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from emc.cli import app


def test_cli_quiz_dry_run_no_diff(
    cli_runner: CliRunner,
    temp_git_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify quiz --dry-run with clean working tree exits 0 with notice."""
    monkeypatch.chdir(temp_git_repo)
    result = cli_runner.invoke(app, ["quiz", "--dry-run"])
    assert result.exit_code == 0
    assert "No diff changes found" in result.stdout


def test_cli_quiz_dry_run_with_staged_secrets(
    cli_runner: CliRunner,
    temp_git_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify quiz --dry-run intercepts secrets and prints redacted output and table."""
    monkeypatch.chdir(temp_git_repo)

    # Stage a file with an Anthropic API key and an EVM hex key
    secret_file = temp_git_repo / "secrets.ts"
    secret_file.write_text(
        'export const key = "sk-ant-api03-abcdef1234567890abcdef1234567890abcdef12345678";\n'
        'export const priv = "0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d";'
        "\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "secrets.ts"], cwd=temp_git_repo, check=True)

    result = cli_runner.invoke(app, ["quiz", "--staged", "--dry-run"])
    assert result.exit_code == 0

    # Verify tables and summaries
    assert "Diff Ingestion & Redaction Summary" in result.stdout
    assert "Detected & Redacted Secrets" in result.stdout
    assert "Dry-run complete" in result.stdout

    # Verify secrets were replaced
    assert "sk-ant-api03" not in result.stdout
    assert "0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d" not in result.stdout
    assert "[REDACTED:anthropic_api_key]" in result.stdout
    assert "[REDACTED:hex_private_key]" in result.stdout


def test_cli_quiz_dry_run_with_stdin(cli_runner: CliRunner) -> None:
    """Verify quiz --dry-run processes diff passed via stdin."""
    stdin_diff = (
        "diff --git a/.env b/.env\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ b/.env\n"
        "@@ -0,0 +1,2 @@\n"
        "+DATABASE_PASSWORD=SuperSecretPass123!\n"
        "+PORT=3000\n"
    )

    result = cli_runner.invoke(app, ["quiz", "--stdin", "--dry-run"], input=stdin_diff)
    assert result.exit_code == 0
    assert "Diff Ingestion & Redaction Summary" in result.stdout
    assert "SuperSecretPass123!" not in result.stdout
    assert "[REDACTED:env_secret]" in result.stdout
    assert "PORT=3000" in result.stdout
