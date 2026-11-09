"""Data models for secret redaction findings and results."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RedactionFinding(BaseModel):
    """A detected secret item found during redaction scanning."""

    rule_id: str
    category: str
    description: str
    matched_text: str
    masked_text: str
    replacement: str
    line_number: int | None = None
    file_path: str | None = None
    start_col: int = 0
    end_col: int = 0


class RedactionResult(BaseModel):
    """Result of running secret redaction over text or diffs."""

    original_text: str
    redacted_text: str
    findings: list[RedactionFinding] = Field(default_factory=list)

    @property
    def redaction_count(self) -> int:
        """Total number of redacted secrets found."""
        return len(self.findings)

    @property
    def has_secrets(self) -> bool:
        """Whether any secrets were detected and redacted."""
        return len(self.findings) > 0
