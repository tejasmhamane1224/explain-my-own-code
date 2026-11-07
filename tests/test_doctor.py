"""Tests for emc doctor diagnostic subsystem."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from emc.cli import app
from emc.doctor import (
    CheckStatus,
    DoctorCheck,
    check_anthropic_api_key,
    check_emc_config,
    check_git_installed,
    check_git_repo,
    check_model_config,
    check_python_runtime,
    mask_secret,
    render_doctor_report,
    run_doctor_checks,
)


def test_mask_secret() -> None:
    """Verify secret masking hides API keys and tokens safely."""
    assert mask_secret(None) == "<not set>"
    assert mask_secret("") == "<not set>"
    assert mask_secret("short") == "***"
    assert mask_secret("sk-ant-api03-abcdefghijklmn1234") == "sk-ant...1234"


def test_check_python_runtime() -> None:
    """Verify Python version check passes on 3.12+."""
    check = check_python_runtime()
    assert check.status == CheckStatus.PASS
    assert "Python" in check.summary
    assert ">= 3.12" in check.summary


def test_check_git_installed() -> None:
    """Verify git executable check finds git."""
    check = check_git_installed()
    assert check.status == CheckStatus.PASS
    assert "git version" in check.summary.lower()


def test_check_git_repo(temp_git_repo: Path, tmp_path: Path) -> None:
    """Verify git repository detection inside and outside a git tree."""
    # Inside repo
    check_inside = check_git_repo(temp_git_repo)
    assert check_inside.status == CheckStatus.PASS
    assert "Active git repository" in check_inside.summary

    # Outside repo (empty dir without .git)
    outside_dir = tmp_path / "not_git"
    outside_dir.mkdir()
    check_outside = check_git_repo(outside_dir)
    assert check_outside.status == CheckStatus.WARN
    assert "Not inside a git repository" in check_outside.summary


def test_check_anthropic_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify Anthropic API key detection and masking."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    check_missing = check_anthropic_api_key()
    assert check_missing.status == CheckStatus.WARN
    assert "not set" in check_missing.summary

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-secret-key-9999")
    check_present = check_anthropic_api_key()
    assert check_present.status == CheckStatus.PASS
    assert "sk-ant...9999" in check_present.summary


def test_check_model_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify model resolution uses EMC_MODEL or default."""
    monkeypatch.delenv("EMC_MODEL", raising=False)
    check_default = check_model_config("claude-3-7-sonnet-latest")
    assert check_default.status == CheckStatus.PASS
    assert "claude-3-7-sonnet-latest" in check_default.summary

    monkeypatch.setenv("EMC_MODEL", "custom-model-id")
    check_custom = check_model_config("claude-3-7-sonnet-latest")
    assert check_custom.status == CheckStatus.PASS
    assert "custom-model-id" in check_custom.summary


def test_check_emc_config(tmp_path: Path) -> None:
    """Verify configuration check detects defaults or .emc.toml."""
    # Defaults
    check_default = check_emc_config(tmp_path)
    assert check_default.status == CheckStatus.PASS
    assert "defaults" in check_default.summary

    # Custom file
    (tmp_path / ".emc.toml").write_text('[emc]\nmode = "gate"\n', encoding="utf-8")
    check_custom = check_emc_config(tmp_path)
    assert check_custom.status == CheckStatus.PASS
    assert "gate" in check_custom.summary


def test_run_doctor_checks() -> None:
    """Verify run_doctor_checks returns complete checklist."""
    checks = run_doctor_checks()
    names = {c.name for c in checks}
    expected = {
        "Python Runtime",
        "Git Installed",
        "Git Repository",
        "Anthropic API Key",
        "EMC Model",
        "EMC Configuration",
        "EMC Local State",
    }
    assert expected.issubset(names)


def test_render_doctor_report_exit_codes() -> None:
    """Verify exit code logic: 0 on PASS/WARN, 1 on FAIL."""
    pass_checks = [
        DoctorCheck(name="C1", status=CheckStatus.PASS, summary="ok"),
        DoctorCheck(name="C2", status=CheckStatus.WARN, summary="warn"),
    ]
    assert render_doctor_report(pass_checks) == 0

    fail_checks = [
        DoctorCheck(name="C1", status=CheckStatus.PASS, summary="ok"),
        DoctorCheck(name="C2", status=CheckStatus.FAIL, summary="error"),
    ]
    assert render_doctor_report(fail_checks) == 1


def test_cli_doctor_command(cli_runner: CliRunner) -> None:
    """Verify emc doctor CLI invocation runs cleanly."""
    result = cli_runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "System Doctor" in result.stdout
    assert "Git Installed" in result.stdout


def test_cli_doctor_json(cli_runner: CliRunner) -> None:
    """Verify emc doctor --json outputs valid JSON structure."""
    result = cli_runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert isinstance(data, list)
    assert len(data) >= 7
    assert any(item["name"] == "Git Installed" for item in data)
