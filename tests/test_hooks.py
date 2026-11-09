"""Acceptance tests for Stage 6 git hooks discovery, installation, and management."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from emc.cli import app
from emc.gate.trailer import save_staged_trailer
from emc.hooks import (
    COMMIT_MSG_SCRIPT,
    PRE_COMMIT_SCRIPT,
    ForeignHookError,
    HookError,
    get_git_hooks_dir,
    install_hooks,
    uninstall_hooks,
)


def test_get_git_hooks_dir_standard_repo(temp_git_repo: Path) -> None:
    """Verify hooks directory discovery in a standard git repository."""
    hooks_dir = get_git_hooks_dir(start_path=temp_git_repo)
    assert hooks_dir is not None
    assert hooks_dir.resolve() == (temp_git_repo / ".git" / "hooks").resolve()


def test_get_git_hooks_dir_subdirectory(temp_git_repo: Path) -> None:
    """Verify hooks directory discovery when called from a deep subdirectory."""
    sub_dir = temp_git_repo / "src" / "deep" / "pkg"
    sub_dir.mkdir(parents=True, exist_ok=True)

    hooks_dir = get_git_hooks_dir(start_path=sub_dir)
    assert hooks_dir is not None
    assert hooks_dir.resolve() == (temp_git_repo / ".git" / "hooks").resolve()


def test_get_git_hooks_dir_outside_repo(tmp_path: Path) -> None:
    """Verify hooks directory discovery outside any git repository returns None and raises."""
    not_repo = tmp_path / "plain_dir"
    not_repo.mkdir()
    assert get_git_hooks_dir(start_path=not_repo) is None
    with pytest.raises(HookError):
        install_hooks(start_path=not_repo)


def test_hook_install_standard_repo(temp_git_repo: Path) -> None:
    """Verify installing pre-commit and commit-msg hooks in a standard repository."""
    result = install_hooks(start_path=temp_git_repo, install_commit_msg=True)
    assert result.pre_commit_installed is True
    assert result.pre_commit_status == "installed"
    assert result.commit_msg_installed is True
    assert result.commit_msg_status == "installed"

    pre_commit_file = result.hooks_dir / "pre-commit"
    commit_msg_file = result.hooks_dir / "commit-msg"

    assert pre_commit_file.is_file()
    assert commit_msg_file.is_file()

    assert pre_commit_file.read_text(encoding="utf-8") == PRE_COMMIT_SCRIPT
    assert commit_msg_file.read_text(encoding="utf-8") == COMMIT_MSG_SCRIPT


def test_hook_install_idempotency(temp_git_repo: Path) -> None:
    """Verify running hook installation repeatedly does not duplicate content or corrupt hooks."""
    res1 = install_hooks(start_path=temp_git_repo)
    assert res1.pre_commit_status == "installed"

    res2 = install_hooks(start_path=temp_git_repo)
    assert res2.pre_commit_status == "already_installed"
    assert res2.commit_msg_status == "already_installed"

    pre_commit = temp_git_repo / ".git" / "hooks" / "pre-commit"
    assert pre_commit.read_text(encoding="utf-8") == PRE_COMMIT_SCRIPT


def test_hook_foreign_hook_protection_and_backup(temp_git_repo: Path) -> None:
    """Verify foreign hooks are protected without force, and backed up to .emc.bak with force."""
    hooks_dir = temp_git_repo / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    foreign_pre = hooks_dir / "pre-commit"
    foreign_content = "#!/bin/sh\necho 'running custom linter'\nexit 0\n"
    foreign_pre.write_text(foreign_content, encoding="utf-8")

    # 1. Without force -> must raise ForeignHookError
    with pytest.raises(ForeignHookError) as exc_info:
        install_hooks(start_path=temp_git_repo, force=False)
    assert "already exists" in str(exc_info.value)
    # File content preserved
    assert foreign_pre.read_text(encoding="utf-8") == foreign_content

    # 2. With force=True -> backs up foreign hook to .emc.bak
    res_force = install_hooks(start_path=temp_git_repo, force=True)
    assert res_force.pre_commit_status == "overwritten"

    bak_file = hooks_dir / "pre-commit.emc.bak"
    assert bak_file.is_file()
    assert bak_file.read_text(encoding="utf-8") == foreign_content
    assert foreign_pre.read_text(encoding="utf-8") == PRE_COMMIT_SCRIPT

    # 3. Uninstall restores foreign hook from backup!
    un_res = uninstall_hooks(start_path=temp_git_repo)
    assert un_res.pre_commit_removed is True
    assert un_res.pre_commit_restored is True
    assert foreign_pre.read_text(encoding="utf-8") == foreign_content
    assert not bak_file.exists()


def test_hook_uninstall_refuses_foreign_without_force(temp_git_repo: Path) -> None:
    """Verify uninstall refuses to delete a foreign hook unless force=True."""
    hooks_dir = temp_git_repo / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    foreign_pre = hooks_dir / "pre-commit"
    foreign_pre.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    with pytest.raises(ForeignHookError):
        uninstall_hooks(start_path=temp_git_repo, force=False)

    assert foreign_pre.exists()

    # With force=True
    un_res = uninstall_hooks(start_path=temp_git_repo, force=True)
    assert un_res.pre_commit_removed is True
    assert not foreign_pre.exists()


def test_git_worktree_hooks_discovery_and_install(temp_git_repo: Path, tmp_path: Path) -> None:
    """Verify hook operations inside a git worktree resolve to the common hooks directory."""
    is_win = sys.platform == "win32"
    # Need initial commit to add a worktree
    initial_file = temp_git_repo / "README.md"
    initial_file.write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(temp_git_repo), check=True, shell=is_win)
    subprocess.run(
        ["git", "commit", "-m", "initial commit"],
        cwd=str(temp_git_repo),
        check=True,
        shell=is_win,
    )

    # Create worktree
    worktree_path = tmp_path / "test_worktree"
    subprocess.run(
        ["git", "worktree", "add", "-b", "feature-wt", str(worktree_path)],
        cwd=str(temp_git_repo),
        capture_output=True,
        check=True,
        shell=is_win,
    )

    # In worktree, .git is a file
    wt_git = worktree_path / ".git"
    assert wt_git.is_file()

    # Discover hooks dir from worktree
    wt_hooks_dir = get_git_hooks_dir(start_path=worktree_path)
    assert wt_hooks_dir is not None
    expected_hooks_dir = (temp_git_repo / ".git" / "hooks").resolve()
    assert wt_hooks_dir.resolve() == expected_hooks_dir

    # Install hooks from inside worktree
    install_res = install_hooks(start_path=worktree_path)
    assert install_res.pre_commit_installed is True
    assert (expected_hooks_dir / "pre-commit").is_file()

    # Uninstall from worktree
    un_res = uninstall_hooks(start_path=worktree_path)
    assert un_res.pre_commit_removed is True
    assert not (expected_hooks_dir / "pre-commit").exists()


def test_cli_hook_commit_msg_integration(
    cli_runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify 'emc hook commit-msg' CLI command injects trailers into commit message files."""
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / ".emc.toml"
    config_file.write_text("[emc]\ncommit_trailer = true\n", encoding="utf-8")

    msg_file = tmp_path / "COMMIT_EDITMSG"
    msg_file.write_text("fix(security): validate account signer\n", encoding="utf-8")

    # 1. Stage a trailer in .emc
    save_staged_trailer("Comprehension: 3/3", target_dir=tmp_path / ".emc")

    # Run emc hook commit-msg
    res = cli_runner.invoke(app, ["hook", "commit-msg", str(msg_file)])
    assert res.exit_code == 0
    content = msg_file.read_text(encoding="utf-8")
    assert "Comprehension: 3/3" in content

    # Verify staged trailer consumed
    assert not (tmp_path / ".emc" / "last_trailer").exists()

    # 2. Explicit --trailer flag
    res_explicit = cli_runner.invoke(
        app,
        ["hook", "commit-msg", str(msg_file), "--trailer", "Comprehension: 100%"],
    )
    assert res_explicit.exit_code == 0
    content_updated = msg_file.read_text(encoding="utf-8")
    assert "Comprehension: 100%" in content_updated
    assert "Comprehension: 3/3" not in content_updated

    # 3. Clean no-op when no staged trailer exists
    clean_msg = tmp_path / "CLEAN_MSG"
    clean_msg.write_text("chore: bump deps\n", encoding="utf-8")
    res_noop = cli_runner.invoke(app, ["hook", "commit-msg", str(clean_msg)])
    assert res_noop.exit_code == 0
    assert clean_msg.read_text(encoding="utf-8") == "chore: bump deps\n"
