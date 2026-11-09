"""Configuration management for explain-my-own-code (emc)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Supported execution modes
EMCMode = Literal["off", "warn", "gate"]

DEFAULT_MODEL = "claude-3-7-sonnet-latest"
CONFIG_FILENAME = ".emc.toml"


class EMCConfig(BaseModel):
    """Configuration settings for emc."""

    model_config = ConfigDict(extra="ignore")

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
        ge=0.0,
        description="Maximum budget per diff quiz session in USD",
    )
    token_budget: int = Field(
        default=50_000,
        gt=0,
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
    trailer_style: Literal["fraction", "percentage", "detailed"] = Field(
        default="fraction",
        description="Format style for commit trailer: 'fraction', 'percentage', or 'detailed'",
    )
    cache_dir: Path = Field(
        default_factory=lambda: Path(".emc/cache"),
        description="Directory for local diff and prompt response caches",
    )
    ledger_path: Path = Field(
        default_factory=lambda: Path(".emc/ledger.jsonl"),
        description="Path to local concept mastery ledger",
    )


class ConfigLoadResult(tuple[EMCConfig, Path | None]):
    """Result of loading .emc.toml.

    Subclasses tuple[EMCConfig, Path | None] for backwards-compatible 2-tuple unpacking
    (`config, path = load_config()`), while also exposing `.config`, `.path`, and `.error`.
    """

    config: EMCConfig
    path: Path | None
    error: str | None

    def __new__(
        cls,
        config: EMCConfig,
        path: Path | None,
        error: str | None = None,
    ) -> ConfigLoadResult:
        instance = super().__new__(cls, (config, path))
        instance.config = config
        instance.path = path
        instance.error = error
        return instance


def find_config_file(start_path: Path | None = None) -> Path | None:
    """Traverse directories upward from start_path to find .emc.toml."""
    current = (start_path or Path.cwd()).resolve()
    for directory in [current, *current.parents]:
        candidate = directory / CONFIG_FILENAME
        if candidate.is_file():
            return candidate
    return None


def load_config(
    config_path: Path | None = None,
    start_dir: Path | None = None,
) -> ConfigLoadResult:
    """Load configuration from .emc.toml if found, otherwise return defaults.

    Returns ConfigLoadResult which unpacks as (config, path) and provides .error if invalid.
    """
    resolved_path = config_path or find_config_file(start_path=start_dir)
    if resolved_path is not None:
        if not resolved_path.is_file():
            return ConfigLoadResult(
                config=EMCConfig(),
                path=resolved_path,
                error=f"Config file not found: {resolved_path}",
            )
        try:
            # Python 3.11+ tomllib
            import tomllib

            with resolved_path.open("rb") as f:
                data = tomllib.load(f)
            # Support top-level or [emc] table
            emc_section = data.get("emc", data)
            if not isinstance(emc_section, dict):
                return ConfigLoadResult(
                    config=EMCConfig(),
                    path=resolved_path,
                    error=(
                        f"Expected a table in {resolved_path.name}, got "
                        f"{type(emc_section).__name__}"
                    ),
                )
            cfg = EMCConfig(**emc_section)
            return ConfigLoadResult(config=cfg, path=resolved_path, error=None)
        except Exception as exc:
            # Return error info alongside fallback defaults
            return ConfigLoadResult(
                config=EMCConfig(),
                path=resolved_path,
                error=f"Failed to parse {resolved_path.name}: {exc}",
            )

    return ConfigLoadResult(config=EMCConfig(), path=None, error=None)
