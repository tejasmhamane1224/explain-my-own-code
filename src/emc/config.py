"""Configuration management for explain-my-own-code (emc)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

# Supported execution modes
EMCMode = Literal["off", "warn", "gate"]

DEFAULT_MODEL = "claude-3-7-sonnet-latest"
CONFIG_FILENAME = ".emc.toml"


class EMCConfig(BaseModel):
    """Configuration settings for emc."""

    mode: EMCMode = Field(
        default="warn",
        description=(
            "Gate enforcement mode: 'off' disables checks, "
            "'warn' alerts without failing, 'gate' blocks commit"
        ),
    )
    model: str = Field(
        default_factory=lambda: os.getenv("EMC_MODEL", DEFAULT_MODEL),
        description="Default LLM model identifier",
    )
    max_cost_dollars: float = Field(
        default=0.50,
        description="Maximum budget per diff quiz session in USD",
    )
    token_budget: int = Field(
        default=50_000,
        description="Maximum token budget per analysis run",
    )
    skip_allowed: bool = Field(
        default=True,
        description="Whether developer is permitted to pass --skip during git pre-commit",
    )
    commit_trailer: bool = Field(
        default=True,
        description="Whether to append 'Comprehension: X/Y' trailer to commit message",
    )
    cache_dir: Path = Field(
        default_factory=lambda: Path(".emc/cache"),
        description="Directory for local diff and prompt response caches",
    )
    ledger_path: Path = Field(
        default_factory=lambda: Path(".emc/ledger.jsonl"),
        description="Path to local concept mastery ledger",
    )


def find_config_file(start_path: Path | None = None) -> Path | None:
    """Traverse directories upward from start_path to find .emc.toml."""
    current = (start_path or Path.cwd()).resolve()
    for directory in [current, *current.parents]:
        candidate = directory / CONFIG_FILENAME
        if candidate.is_file():
            return candidate
    return None


def load_config(config_path: Path | None = None) -> tuple[EMCConfig, Path | None]:
    """Load configuration from .emc.toml if found, otherwise return defaults."""
    resolved_path = config_path or find_config_file()
    if resolved_path is not None and resolved_path.is_file():
        try:
            # Python 3.11+ tomllib
            import tomllib

            with resolved_path.open("rb") as f:
                data = tomllib.load(f)
            # Support top-level or [emc] table
            emc_section = data.get("emc", data)
            return EMCConfig(**emc_section), resolved_path
        except Exception:
            # Fall back to default config if file is corrupt
            return EMCConfig(), resolved_path

    return EMCConfig(), None
