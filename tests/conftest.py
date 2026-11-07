"""Pytest configuration and common fixtures."""

import os
from pathlib import Path
from typing import Generator

import pytest
from typer.testing import CliRunner


@pytest.fixture
def cli_runner() -> CliRunner:
    """Fixture providing Typer CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Generator[Path, None, None]:
    """Fixture providing a temporary clean git repository."""
    import subprocess
    import sys

    repo_dir = tmp_path / "git_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    is_win = sys.platform == "win32"
    subprocess.run(
        ["git", "init"], cwd=str(repo_dir), capture_output=True, check=True, shell=is_win
    )
    subprocess.run(
        ["git", "config", "user.name", "Test Committer"],
        cwd=str(repo_dir),
        capture_output=True,
        check=True,
        shell=is_win,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(repo_dir),
        capture_output=True,
        check=True,
        shell=is_win,
    )
    yield repo_dir


@pytest.fixture
def clean_env() -> Generator[None, None, None]:
    """Fixture ensuring isolated environment variables."""
    old_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(old_env)
