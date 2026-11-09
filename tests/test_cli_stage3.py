"""Tests for Stage 3 CLI commands: emc generate and emc quiz --dry-run --generate."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from emc.cli import app

SAMPLE_DIFF = (
    "diff --git a/programs/vault/src/lib.rs b/programs/vault/src/lib.rs\n"
    "--- a/programs/vault/src/lib.rs\n"
    "+++ b/programs/vault/src/lib.rs\n"
    "@@ -20,4 +20,6 @@\n"
    "+#[derive(Accounts)]\n"
    "+pub struct VaultWithdraw<'info> {\n"
    "+    pub authority: AccountInfo<'info>,\n"
    "+    pub vault: Account<'info, VaultData>,\n"
    "+}\n"
)


def test_cli_quiz_dry_run_displays_planned_questions(cli_runner: CliRunner) -> None:
    """Verify emc quiz --dry-run includes Planned Comprehension Questions table."""
    result = cli_runner.invoke(app, ["quiz", "--stdin", "--dry-run"], input=SAMPLE_DIFF)
    assert result.exit_code == 0
    assert "Planned Comprehension Questions (Stage 3 Planning)" in result.stdout
    assert "anchor.signer" in result.stdout
    assert "consequence" in result.stdout
    assert "templated" in result.stdout


def test_cli_quiz_dry_run_with_generate(cli_runner: CliRunner) -> None:
    """Verify emc quiz --dry-run --generate generates questions and shows gate results."""
    result = cli_runner.invoke(
        app,
        ["quiz", "--stdin", "--dry-run", "--generate"],
        input=SAMPLE_DIFF,
    )
    assert result.exit_code == 0
    assert "Generated Questions & Quality Gate Results" in result.stdout
    assert "PASSED" in result.stdout


def test_cli_generate_command_text(cli_runner: CliRunner) -> None:
    """Verify emc generate produces table with generated questions and quality gate status."""
    result = cli_runner.invoke(app, ["generate", "--stdin"], input=SAMPLE_DIFF)
    assert result.exit_code == 0
    assert "Generated Comprehension Questions" in result.stdout
    assert "consequence" in result.stdout
    assert "PASSED" in result.stdout


def test_cli_generate_command_json(cli_runner: CliRunner) -> None:
    """Verify emc generate --json outputs machine-readable JSON with questions and usage."""
    result = cli_runner.invoke(app, ["generate", "--stdin", "--json"], input=SAMPLE_DIFF)
    assert result.exit_code == 0

    data = json.loads(result.stdout)
    assert "questions" in data
    assert "total_generated" in data
    assert data["total_generated"] >= 1
    assert data["questions"][0]["concept_id"] == "anchor.signer_check"
    assert "usage" in data
    assert "cost_usd" in data
