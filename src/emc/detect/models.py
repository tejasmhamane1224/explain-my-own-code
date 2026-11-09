"""Data models for detector findings, risk severities, and ranked hunks."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from emc.ingest.models import DiffHunk


class RiskSeverity(str, Enum):
    """Severity classification for detector findings."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

    @property
    def weight(self) -> float:
        """Numerical weight for risk scoring."""
        weights = {
            RiskSeverity.CRITICAL: 10.0,
            RiskSeverity.HIGH: 5.0,
            RiskSeverity.MEDIUM: 2.5,
            RiskSeverity.LOW: 1.0,
            RiskSeverity.INFO: 0.5,
        }
        return weights.get(self, 1.0)


class DetectionFinding(BaseModel):
    """A single finding flagged by a deterministic risk rule."""

    rule_id: str
    concept_id: str
    category: str
    severity: RiskSeverity
    title: str
    message: str
    file_path: str
    line_number: int | None = None
    snippet: str = ""
    recommendation: str = ""
    hunk_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert finding to standard dictionary representation."""
        return {
            "rule_id": self.rule_id,
            "concept_id": self.concept_id,
            "category": self.category,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "snippet": self.snippet,
            "recommendation": self.recommendation,
            "hunk_index": self.hunk_index,
        }


class RankedHunk(BaseModel):
    """A diff hunk ranked by calculated risk score and associated findings."""

    hunk: DiffHunk
    file_path: str
    rank: int = 1
    risk_score: float = 0.0
    findings: list[DetectionFinding] = Field(default_factory=list)
    primary_concept: str | None = None
    file_multiplier: float = 1.0

    @property
    def line_range(self) -> str:
        """Format 1-indexed target line range string (e.g. L45-L60)."""
        start = self.hunk.new_start
        count = self.hunk.new_lines
        if count <= 1:
            return f"L{start}"
        return f"L{start}-L{start + count - 1}"

    @property
    def triggered_rule_ids(self) -> list[str]:
        """Unique list of rule IDs triggered on this hunk."""
        seen = set()
        result = []
        for f in self.findings:
            if f.rule_id not in seen:
                seen.add(f.rule_id)
                result.append(f.rule_id)
        return result


class DetectionReport(BaseModel):
    """Comprehensive analysis report containing all findings and ranked hunks."""

    findings: list[DetectionFinding] = Field(default_factory=list)
    ranked_hunks: list[RankedHunk] = Field(default_factory=list)

    @property
    def total_findings(self) -> int:
        return len(self.findings)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == RiskSeverity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == RiskSeverity.HIGH)

    @property
    def medium_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == RiskSeverity.MEDIUM)

    @property
    def low_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == RiskSeverity.LOW)

    @property
    def highest_risk_score(self) -> float:
        return max((h.risk_score for h in self.ranked_hunks), default=0.0)
