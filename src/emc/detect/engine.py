"""Detector engine coordinating all static risk detectors and taxonomy validation."""

from __future__ import annotations

from emc.detect.generic import detect_generic_risks
from emc.detect.models import DetectionFinding, DetectionReport
from emc.detect.ranking import rank_hunks
from emc.detect.rust_anchor import detect_rust_anchor_risks
from emc.detect.taxonomy import get_taxonomy
from emc.detect.ts_wallet import detect_ts_wallet_risks
from emc.ingest.models import FileDiff, IngestResult


def detect_file_risks(file_diff: FileDiff) -> list[DetectionFinding]:
    """Run all detector suites against a single file diff."""
    findings: list[DetectionFinding] = []

    # 1. Rust and Anchor smart contract rules
    findings.extend(detect_rust_anchor_risks(file_diff))

    # 2. TypeScript and Solana wallet rules
    findings.extend(detect_ts_wallet_risks(file_diff))

    # 3. Generic code smells and security bypasses
    findings.extend(detect_generic_risks(file_diff))

    return findings


def detect_risks(ingest_result: IngestResult) -> list[DetectionFinding]:
    """Run all static risk detectors across an ingested diff."""
    findings: list[DetectionFinding] = []
    taxonomy = get_taxonomy()

    for file_diff in ingest_result.files:
        file_findings = detect_file_risks(file_diff)
        for f in file_findings:
            # Validate concept alignment
            if taxonomy.contains(f.concept_id):
                # Optionally verify default severity
                concept = taxonomy.get(f.concept_id)
                if concept and not f.recommendation:
                    f.recommendation = concept.remediation
            findings.append(f)

    # Deduplicate findings by (rule_id, file_path, line_number)
    deduped: list[DetectionFinding] = []
    seen = set()
    for f in findings:
        key = (f.rule_id, f.file_path, f.line_number)
        if key not in seen:
            seen.add(key)
            deduped.append(f)

    return deduped


def run_detector_pipeline(ingest_result: IngestResult) -> DetectionReport:
    """Execute complete detector suite and rank hunks by risk score."""
    findings = detect_risks(ingest_result)
    ranked_hunks = rank_hunks(ingest_result, findings)
    return DetectionReport(findings=findings, ranked_hunks=ranked_hunks)
