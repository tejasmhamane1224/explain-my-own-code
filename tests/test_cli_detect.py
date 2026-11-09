"""Tests for CLI detect command and quiz --dry-run risk tables."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from emc.cli import app


def test_cli_detect_no_diff(
    cli_runner: CliRunner, temp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify emc detect reports no changes when tree is clean."""
    monkeypatch.chdir(temp_git_repo)
    result = cli_runner.invoke(app, ["detect"])
    assert result.exit_code == 0
    assert "No diff changes found" in result.stdout


def test_cli_detect_with_stdin_diff(cli_runner: CliRunner) -> None:
    """Verify emc detect flags risks and ranks hunks from stdin."""
    stdin_diff = (
        "diff --git a/programs/vault/src/lib.rs b/programs/vault/src/lib.rs\n"
        "--- a/programs/vault/src/lib.rs\n"
        "+++ b/programs/vault/src/lib.rs\n"
        "@@ -10,4 +10,5 @@\n"
        " #[derive(Accounts)]\n"
        " pub struct WithdrawFunds<'info> {\n"
        "+    pub authority: AccountInfo<'info>,\n"
        "     pub vault: Account<'info, Vault>,\n"
        " }\n"
    )

    result = cli_runner.invoke(app, ["detect", "--stdin"], input=stdin_diff)
    assert result.exit_code == 0
    assert "Diff Detection & Ranking Summary" in result.stdout
    assert "Detected Static Risk Findings" in result.stdout
    assert "Ranked Diff Hunks by Risk Score" in result.stdout
    assert "anchor.missing_signer" in result.stdout
    assert "CRITICAL" in result.stdout


def test_cli_detect_json_output(cli_runner: CliRunner) -> None:
    """Verify emc detect --json outputs structured report JSON."""
    stdin_diff = (
        "diff --git a/src/wallet.ts b/src/wallet.ts\n"
        "--- a/src/wallet.ts\n"
        "+++ b/src/wallet.ts\n"
        "@@ -1,2 +1,3 @@\n"
        "+const rpc = 'https://api.mainnet-beta.solana.com';\n"
    )

    result = cli_runner.invoke(app, ["detect", "--stdin", "--json"], input=stdin_diff)
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["total_findings"] >= 1
    assert data["high_count"] >= 1
    assert len(data["findings"]) >= 1
    assert data["findings"][0]["rule_id"] == "ts.hardcoded_rpc"
    assert data["findings"][0]["concept_id"] == "ts.rpc_security"
    assert len(data["ranked_hunks"]) >= 1


def test_cli_quiz_dry_run_displays_risk_tables(cli_runner: CliRunner) -> None:
    """Verify quiz --dry-run displays static risk findings and ranked hunks."""
    diff_with_risk = (
        "diff --git a/src/auth.py b/src/auth.py\n"
        "--- a/src/auth.py\n"
        "+++ b/src/auth.py\n"
        "@@ -1,2 +1,3 @@\n"
        "+skip_auth = True\n"
    )

    result = cli_runner.invoke(app, ["quiz", "--stdin", "--dry-run"], input=diff_with_risk)
    assert result.exit_code == 0
    assert "Diff Ingestion & Redaction Summary" in result.stdout
    assert "Detected Static Risk Findings" in result.stdout
    assert "Ranked Diff Hunks by Risk Score" in result.stdout
    assert "generic.bypass_flag" in result.stdout
    assert "generic.bypas" in result.stdout
