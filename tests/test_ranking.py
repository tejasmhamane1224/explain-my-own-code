"""Tests for hunk risk ranking engine."""

from __future__ import annotations

from emc.detect.models import DetectionFinding, RiskSeverity
from emc.detect.ranking import compute_file_multiplier, rank_hunks
from emc.ingest.models import DiffHunk, DiffLine, FileDiff, IngestResult


def test_compute_file_multiplier() -> None:
    """Verify file multiplier accurately reflects path risk profile."""
    # Smart contracts
    assert compute_file_multiplier("programs/escrow/src/lib.rs") == 1.8
    assert compute_file_multiplier("contracts/TokenVault.rs") == 1.8

    # TS wallet / auth files
    assert compute_file_multiplier("src/wallet/signer.ts") == 1.5
    assert compute_file_multiplier("src/auth/jwt.ts") == 1.5
    assert compute_file_multiplier("src/transactions/builder.ts") == 1.5

    # Test / documentation files
    assert compute_file_multiplier("tests/test_vault.rs") == 0.3
    assert compute_file_multiplier("docs/architecture.md") == 0.3
    assert compute_file_multiplier("fixtures/injections/test.diff") == 0.3

    # Generic src files
    assert compute_file_multiplier("src/utils/formatter.py") == 1.0


def test_hunk_ranking_prioritizes_higher_risk() -> None:
    """Verify hunks with critical findings are ranked above benign or lower risk hunks."""
    line_high = DiffLine(
        line_type="+",
        content="pub authority: AccountInfo<'info>,",
        raw="+pub authority: AccountInfo<'info>,",
        new_line_number=10,
    )
    line_benign = DiffLine(
        line_type="+", content="let x = 1;", raw="+let x = 1;", new_line_number=5
    )

    hunk_critical = DiffHunk(
        header="@@ -1,5 +1,6 @@",
        old_start=1,
        old_lines=5,
        new_start=1,
        new_lines=6,
        lines=[line_high],
    )
    hunk_low = DiffHunk(
        header="@@ -1,5 +1,6 @@",
        old_start=1,
        old_lines=5,
        new_start=1,
        new_lines=6,
        lines=[line_benign],
    )

    file_diff = FileDiff(
        old_path="programs/vault/src/lib.rs",
        new_path="programs/vault/src/lib.rs",
        hunks=[hunk_low, hunk_critical],
    )

    ingest = IngestResult(files=[file_diff], raw_diff="dummy", source="test")

    critical_finding = DetectionFinding(
        rule_id="anchor.missing_signer",
        concept_id="anchor.signer_check",
        category="rust_anchor",
        severity=RiskSeverity.CRITICAL,
        title="Missing Signer",
        message="Critical missing signer",
        file_path="programs/vault/src/lib.rs",
        line_number=10,
        snippet="pub authority: AccountInfo<'info>,",
        hunk_index=1,
    )

    ranked = rank_hunks(ingest, [critical_finding])

    assert len(ranked) == 2
    # First ranked hunk must be hunk_critical
    assert ranked[0].rank == 1
    assert ranked[0].risk_score > ranked[1].risk_score
    assert ranked[0].primary_concept == "anchor.signer_check"
    assert "anchor.missing_signer" in ranked[0].triggered_rule_ids
    assert ranked[1].rank == 2
    assert ranked[1].primary_concept is None


def test_hunk_line_range_string() -> None:
    """Verify line_range property formats single lines and multi-line spans."""
    single_hunk = DiffHunk(
        header="@@ -10 +10 @@",
        old_start=10,
        old_lines=1,
        new_start=10,
        new_lines=1,
        lines=[],
    )
    ranked_single = rank_hunks(
        IngestResult(
            files=[FileDiff(new_path="lib.rs", hunks=[single_hunk])],
            raw_diff="",
            source="",
        ),
        [],
    )[0]
    assert ranked_single.line_range == "L10"

    multi_hunk = DiffHunk(
        header="@@ -10,5 +10,5 @@",
        old_start=10,
        old_lines=5,
        new_start=10,
        new_lines=5,
        lines=[],
    )
    ranked_multi = rank_hunks(
        IngestResult(
            files=[FileDiff(new_path="lib.rs", hunks=[multi_hunk])],
            raw_diff="",
            source="",
        ),
        [],
    )[0]
    assert ranked_multi.line_range == "L10-L14"
