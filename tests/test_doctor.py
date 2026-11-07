"""Tests for emc doctor diagnostic subsystem."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from emc.cli import app
from emc.doctor import (
    CheckStatus,
    DoctorCheck,
    check_anthropic_api_key,
    check_cache_and_ledger,
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
    """Verify secret masking hides API keys and tokens safely without leaking characters."""
    assert mask_secret(None) == "<not set>"
    assert mask_secret("") == "<not set>"
    assert mask_secret("   ") == "<not set>"
    assert mask_secret("short") == "***"
    assert mask_secret("123456789") == "***"
    assert mask_secret("1234567890123") == "***"
    # Long keys: prefix and suffix shown, middle masked
    assert mask_secret("sk-ant-api03-abcdefghijklmn1234") == "sk-ant...1234"


def test_check_python_runtime() -> None:
    """Verify Python version check passes on 3.12+ and fails on older versions."""
    check = check_python_runtime()
    assert check.status == CheckStatus.PASS
    assert "Python" in check.summary
    assert ">= 3.12" in check.summary

    # Test old python version failure
    with patch("sys.version_info", (3, 11, 4, "final", 0)):
        old_check = check_python_runtime()
        assert old_check.status == CheckStatus.FAIL
        assert "unsupported" in old_check.summary


def test_check_git_installed() -> None:
    """Verify git executable check finds git or reports failure."""
    check = check_git_installed()
    assert check.status == CheckStatus.PASS
    assert "git version" in check.summary.lower()

    # Mock git missing
    with patch("shutil.which", return_value=None):
        missing_check = check_git_installed()
        assert missing_check.status == CheckStatus.FAIL
        assert "not found" in missing_check.summary


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

    # Git executable missing
    with patch("shutil.which", return_value=None):
        no_git_check = check_git_repo(temp_git_repo)
        assert no_git_check.status == CheckStatus.WARN
        assert "Git executable not found" in no_git_check.summary


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
    """Verify model resolution uses EMC_MODEL or default, and rejects empty strings."""
    monkeypatch.delenv("EMC_MODEL", raising=False)
    check_default = check_model_config("claude-3-7-sonnet-latest")
    assert check_default.status == CheckStatus.PASS
    assert "claude-3-7-sonnet-latest" in check_default.summary

    monkeypatch.setenv("EMC_MODEL", "custom-model-id")
    check_custom = check_model_config("claude-3-7-sonnet-latest")
    assert check_custom.status == CheckStatus.PASS
    assert "custom-model-id" in check_custom.summary

    # Empty model name should fail
    monkeypatch.setenv("EMC_MODEL", "   ")
    check_empty = check_model_config("")
    assert check_empty.status == CheckStatus.FAIL
    assert "empty or invalid" in check_empty.summary


def test_check_emc_config(tmp_path: Path) -> None:
    """Verify configuration check detects defaults, valid files, and corrupted files."""
    # Defaults
    check_default = check_emc_config(tmp_path)
    assert check_default.status == CheckStatus.PASS
    assert "defaults" in check_default.summary

    # Valid custom file
    config_file = tmp_path / ".emc.toml"
    config_file.write_text('[emc]\nmode = "gate"\n', encoding="utf-8")
    check_custom = check_emc_config(tmp_path)
    assert check_custom.status == CheckStatus.PASS
    assert "gate" in check_custom.summary

    # Corrupted TOML syntax
    config_file.write_text("invalid = [syntax\n", encoding="utf-8")
    check_corrupt = check_emc_config(tmp_path)
    assert check_corrupt.status == CheckStatus.FAIL
    assert "Invalid configuration" in check_corrupt.summary

    # Invalid mode schema
    config_file.write_text('[emc]\nmode = "unsupported_mode"\n', encoding="utf-8")
    check_invalid_schema = check_emc_config(tmp_path)
    assert check_invalid_schema.status == CheckStatus.FAIL
    assert "Invalid configuration" in check_invalid_schema.summary


def test_check_cache_and_ledger(tmp_path: Path) -> None:
    """Verify .emc state diagnostics handle uninitialized, existing, and invalid states."""
    # Uninitialized
    check_uninit = check_cache_and_ledger(tmp_path)
    assert check_uninit.status == CheckStatus.PASS
    assert "created on first quiz" in check_uninit.summary

    # Initialized directory
    emc_dir = tmp_path / ".emc"
    emc_dir.mkdir()
    check_dir = check_cache_and_ledger(tmp_path)
    assert check_dir.status == CheckStatus.PASS
    assert "ledger not initialized" in check_dir.summary

    # Initialized with ledger
    (emc_dir / "ledger.jsonl").write_text('{"concept": "anchor.signer"}\n', encoding="utf-8")
    check_with_ledger = check_cache_and_ledger(tmp_path)
    assert check_with_ledger.status == CheckStatus.PASS
    assert "ledger exists" in check_with_ledger.summary

    # File instead of directory
    file_path = tmp_path / "not_dir_emc"
    file_path.write_text("hello", encoding="utf-8")
    # Subpath check
    test_cwd = tmp_path / "sub"
    test_cwd.mkdir()
    (test_cwd / ".emc").write_text("not a dir", encoding="utf-8")
    check_not_dir = check_cache_and_ledger(test_cwd)
    assert check_not_dir.status == CheckStatus.WARN
    assert "not a directory" in check_not_dir.summary


def test_run_doctor_checks(tmp_path: Path) -> None:
    """Verify run_doctor_checks returns complete checklist and honors cwd."""
    checks = run_doctor_checks(cwd=tmp_path)
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


def test_cli_doctor_json_failure_exit_code(cli_runner: CliRunner) -> None:
    """Verify emc doctor --json returns exit code 1 when a check fails."""
    with patch("emc.doctor.check_python_runtime") as mock_check:
        mock_check.return_value = DoctorCheck(
            name="Python Runtime",
            status=CheckStatus.FAIL,
            summary="Python 3.10 is unsupported",
        )
        result = cli_runner.invoke(app, ["doctor", "--json"])
        assert result.exit_code == 1
        data = json.loads(result.stdout)
        assert any(item["status"] == "FAIL" for item in data)
