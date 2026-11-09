"""Path filtering for diffs using .emcignore and default lock/binary ignore rules."""

from __future__ import annotations

from pathlib import Path

import pathspec

from emc.ingest.models import FileDiff

DEFAULT_IGNORE_PATTERNS = [
    # Package lockfiles
    "*.lock",
    "package-lock.json",
    "Cargo.lock",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "composer.lock",
    "Gemfile.lock",
    # Minified assets & source maps
    "*.min.js",
    "*.min.css",
    "*.map",
    # Media and image binaries
    "*.svg",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.ico",
    "*.pdf",
    "*.wasm",
    # Common build output and dependency folders
    "node_modules/**",
    "target/**",
    "dist/**",
    "build/**",
    ".git/**",
    ".emc/**",
    ".mypy_cache/**",
    ".pytest_cache/**",
    ".ruff_cache/**",
    "__pycache__/**",
]


def load_ignore_spec(
    ignore_file: Path | None = None,
    cwd: Path | None = None,
) -> pathspec.PathSpec:
    """Load gitwildmatch PathSpec combining default rules and .emcignore file if found."""
    patterns = list(DEFAULT_IGNORE_PATTERNS)

    target_file = ignore_file
    if target_file is None:
        base_dir = cwd or Path.cwd()
        candidate = base_dir / ".emcignore"
        if candidate.is_file():
            target_file = candidate

    if target_file and target_file.is_file():
        try:
            content = target_file.read_text(encoding="utf-8")
            for line in content.splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    patterns.append(stripped)
        except Exception:
            pass

    return pathspec.PathSpec.from_lines("gitignore", patterns)


def filter_ignored_files(
    files: list[FileDiff],
    ignore_file: Path | None = None,
    cwd: Path | None = None,
) -> tuple[list[FileDiff], list[str]]:
    """Filter out files matching .emcignore or default rules, returning (kept, ignored_paths)."""
    spec = load_ignore_spec(ignore_file=ignore_file, cwd=cwd)
    kept: list[FileDiff] = []
    ignored: list[str] = []

    for file_diff in files:
        path = file_diff.path
        # Normalize path separators for pathspec
        norm_path = path.replace("\\", "/")
        if spec.match_file(norm_path):
            ignored.append(path)
        else:
            kept.append(file_diff)

    return kept, ignored
