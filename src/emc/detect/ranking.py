"""Hunk risk ranking engine prioritizing high-risk diff hunks for question generation."""

from __future__ import annotations

import re

from emc.detect.models import DetectionFinding, RankedHunk
from emc.ingest.models import IngestResult

# Keywords indicating critical file paths
RE_SMART_CONTRACT = re.compile(r"(\.rs$|programs/|contracts/)", re.IGNORECASE)
RE_WALLET_AUTH = re.compile(
    r"(wallet|token|transfer|keypair|auth|signer|vault|transaction|escrow|settlement)",
    re.IGNORECASE,
)
RE_TEST_OR_DOC = re.compile(r"(tests?/|fixtures/|docs?/|\.md$|\.ya?ml$|__tests__/)", re.IGNORECASE)


def compute_file_multiplier(file_path: str) -> float:
    """Compute file importance risk multiplier based on path conventions."""
    if RE_TEST_OR_DOC.search(file_path):
        return 0.3
    if RE_SMART_CONTRACT.search(file_path):
        return 1.8
    if RE_WALLET_AUTH.search(file_path):
        return 1.5
    return 1.0


def rank_hunks(
    ingest_result: IngestResult,
    findings: list[DetectionFinding],
) -> list[RankedHunk]:
    """Rank all diff hunks by calculated risk score in descending order."""
    ranked: list[RankedHunk] = []

    # Map findings by (file_path, hunk_index)
    finding_map: dict[tuple[str, int], list[DetectionFinding]] = {}
    for f in findings:
        key = (f.file_path, f.hunk_index if f.hunk_index is not None else 0)
        finding_map.setdefault(key, []).append(f)

    for file_diff in ingest_result.files:
        path = file_diff.path
        multiplier = compute_file_multiplier(path)

        for hunk_idx, hunk in enumerate(file_diff.hunks):
            hunk_findings = finding_map.get((path, hunk_idx), [])

            # Severity score sum
            findings_score = sum(f.severity.weight for f in hunk_findings)

            # Change volume score (additions weighted higher than deletions)
            adds = len(hunk.added_lines)
            dels = len(hunk.deleted_lines)
            volume_score = (adds * 0.1) + (dels * 0.03)

            # Base score combined with multiplier
            total_score = round((findings_score + volume_score) * multiplier, 2)

            # Determine primary concept
            primary_concept = None
            if hunk_findings:
                # Pick highest severity concept
                sorted_f = sorted(hunk_findings, key=lambda x: x.severity.weight, reverse=True)
                primary_concept = sorted_f[0].concept_id

            ranked.append(
                RankedHunk(
                    hunk=hunk,
                    file_path=path,
                    rank=1,
                    risk_score=total_score,
                    findings=hunk_findings,
                    primary_concept=primary_concept,
                    file_multiplier=multiplier,
                )
            )

    # Sort descending by risk score, then additions count
    ranked.sort(
        key=lambda rh: (rh.risk_score, len(rh.hunk.added_lines), len(rh.findings)),
        reverse=True,
    )

    # Assign sequential ranks 1..N
    for idx, rh in enumerate(ranked, start=1):
        rh.rank = idx

    return ranked
