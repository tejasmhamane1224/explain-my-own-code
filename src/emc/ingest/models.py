"""Data models for parsed diffs, hunks, and lines."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DiffLineType = Literal["+", "-", " ", "\\"]


class DiffLine(BaseModel):
    """A single line within a diff hunk."""

    line_type: DiffLineType
    content: str
    raw: str
    old_line_number: int | None = None
    new_line_number: int | None = None


class DiffHunk(BaseModel):
    """A single contiguous hunk within a file diff."""

    header: str
    old_start: int
    old_lines: int
    new_start: int
    new_lines: int
    section_header: str = ""
    lines: list[DiffLine] = Field(default_factory=list)

    @property
    def added_lines(self) -> list[DiffLine]:
        """Return all added lines in this hunk."""
        return [line for line in self.lines if line.line_type == "+"]

    @property
    def deleted_lines(self) -> list[DiffLine]:
        """Return all deleted lines in this hunk."""
        return [line for line in self.lines if line.line_type == "-"]

    @property
    def context_lines(self) -> list[DiffLine]:
        """Return all context lines in this hunk."""
        return [line for line in self.lines if line.line_type == " "]

    @property
    def line_count(self) -> int:
        """Total number of lines in this hunk."""
        return len(self.lines)

    @property
    def content(self) -> str:
        """Reconstruct full text of hunk."""
        return "\n".join(line.raw for line in self.lines)


class FileDiff(BaseModel):
    """Diff representation for a single file."""

    old_path: str | None = None
    new_path: str | None = None
    is_new: bool = False
    is_deleted: bool = False
    is_binary: bool = False
    is_rename: bool = False
    raw_header: str = ""
    hunks: list[DiffHunk] = Field(default_factory=list)

    @property
    def path(self) -> str:
        """Resolved effective file path."""
        return self.new_path or self.old_path or "unknown"

    @property
    def total_additions(self) -> int:
        """Total added lines across all hunks."""
        return sum(len(hunk.added_lines) for hunk in self.hunks)

    @property
    def total_deletions(self) -> int:
        """Total deleted lines across all hunks."""
        return sum(len(hunk.deleted_lines) for hunk in self.hunks)


class IngestResult(BaseModel):
    """Result of diff ingestion, splitting, and filtering."""

    files: list[FileDiff] = Field(default_factory=list)
    raw_diff: str = ""
    source: str = "staged"
    ignored_files: list[str] = Field(default_factory=list)
    truncated: bool = False
    truncation_reason: str | None = None

    @property
    def total_files(self) -> int:
        """Count of active included file diffs."""
        return len(self.files)

    @property
    def total_hunks(self) -> int:
        """Count of hunks across all active files."""
        return sum(len(f.hunks) for f in self.files)

    @property
    def total_additions(self) -> int:
        """Total added lines across all active files."""
        return sum(f.total_additions for f in self.files)

    @property
    def total_deletions(self) -> int:
        """Total deleted lines across all active files."""
        return sum(f.total_deletions for f in self.files)

    @property
    def is_empty(self) -> bool:
        """Check whether diff contains no active file changes."""
        return len(self.files) == 0
