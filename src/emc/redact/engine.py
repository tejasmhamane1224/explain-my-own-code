"""Secret redaction engine coordinating detection, filtering, and text replacement."""

from __future__ import annotations

from emc.ingest.caps import apply_caps
from emc.ingest.ignore import filter_ignored_files
from emc.ingest.models import IngestResult
from emc.ingest.parser import parse_unified_diff
from emc.redact.models import RedactionFinding, RedactionResult
from emc.redact.rules import SCAN_RULE_FUNCTIONS


class Redactor:
    """Coordinates multi-rule scanning, deduplication, and replacement of sensitive secrets."""

    def __init__(self) -> None:
        self.rules = list(SCAN_RULE_FUNCTIONS)

    def scan_text(self, text: str, file_path: str | None = None) -> list[RedactionFinding]:
        """Scan text across all rules and return sorted, non-overlapping findings."""
        raw_findings: list[RedactionFinding] = []
        for rule_fn in self.rules:
            try:
                rule_findings = rule_fn(text)
                raw_findings.extend(rule_findings)
            except Exception:
                pass

        if not raw_findings:
            return []

        # Sort by start position ascending, then length descending
        raw_findings.sort(key=lambda f: (f.start_col, -(f.end_col - f.start_col)))

        # Resolve overlaps by favoring the first / longer match
        filtered_findings: list[RedactionFinding] = []
        last_end = -1
        for finding in raw_findings:
            if finding.start_col >= last_end:
                filtered_findings.append(finding)
                last_end = finding.end_col

        # Compute line numbers
        newline_offsets: list[int] = [0]
        for idx, char in enumerate(text):
            if char == "\n":
                newline_offsets.append(idx + 1)

        def get_line_number(col: int) -> int:
            # Binary search or scan
            line_no = 1
            for offset in newline_offsets:
                if offset <= col:
                    line_no = newline_offsets.index(offset) + 1
                else:
                    break
            return line_no

        for finding in filtered_findings:
            finding.line_number = get_line_number(finding.start_col)
            finding.file_path = file_path

        return filtered_findings

    def redact_text(self, text: str, file_path: str | None = None) -> RedactionResult:
        """Scan and replace all sensitive secrets in text, returning RedactionResult."""
        findings = self.scan_text(text, file_path=file_path)
        if not findings:
            return RedactionResult(original_text=text, redacted_text=text, findings=[])

        # Replace in reverse order so character offsets remain valid
        sorted_for_replace = sorted(findings, key=lambda f: f.start_col, reverse=True)
        chars = list(text)
        for finding in sorted_for_replace:
            chars[finding.start_col : finding.end_col] = list(finding.replacement)

        redacted_str = "".join(chars)
        return RedactionResult(
            original_text=text,
            redacted_text=redacted_str,
            findings=findings,
        )

    def redact_ingest_result(
        self,
        ingest: IngestResult,
    ) -> tuple[IngestResult, list[RedactionFinding]]:
        """Redact raw_diff and produce an updated IngestResult with redacted hunks."""
        result = self.redact_text(ingest.raw_diff)
        if not result.has_secrets:
            return ingest, []

        # Re-parse redacted diff to update FileDiff, DiffHunk, and DiffLine instances
        redacted_files = parse_unified_diff(result.redacted_text)
        kept_files, _ = filter_ignored_files(redacted_files)
        capped_files, is_truncated, reason = apply_caps(kept_files)

        updated_ingest = IngestResult(
            files=capped_files,
            raw_diff=result.redacted_text,
            source=ingest.source,
            ignored_files=ingest.ignored_files,
            truncated=is_truncated or ingest.truncated,
            truncation_reason=reason or ingest.truncation_reason,
        )

        return updated_ingest, result.findings


def redact_diff(diff_text: str) -> RedactionResult:
    """Convenience functional helper to redact diff text directly."""
    return Redactor().redact_text(diff_text)
