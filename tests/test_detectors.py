"""Tests for deterministic static risk detectors using positive and negative fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from emc.detect import detect_risks, get_taxonomy
from emc.ingest import IngestResult, parse_unified_diff


def _load_manifest() -> list[dict[str, Any]]:
    manifest_path = (
        Path(__file__).resolve().parent.parent / "fixtures" / "detectors" / "manifest.json"
    )
    assert manifest_path.is_file(), f"Manifest file not found: {manifest_path}"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    fixtures = data.get("fixtures", [])
    assert len(fixtures) == 32, f"Expected 32 fixtures in manifest, found {len(fixtures)}"
    return fixtures


FIXTURES = _load_manifest()
POSITIVE_FIXTURES = [f for f in FIXTURES if f["fixture_type"] == "positive"]
NEGATIVE_FIXTURES = [f for f in FIXTURES if f["fixture_type"] == "negative"]


def test_taxonomy_contains_all_manifest_concepts() -> None:
    """Verify that every concept in manifest is registered in concepts.yaml taxonomy."""
    taxonomy = get_taxonomy()
    for item in FIXTURES:
        concept_id = item["concept_id"]
        assert taxonomy.contains(concept_id), f"Concept '{concept_id}' missing in taxonomy"


@pytest.mark.parametrize(
    "fixture_info", POSITIVE_FIXTURES, ids=[f["name"] for f in POSITIVE_FIXTURES]
)
def test_positive_detector_fixtures(fixture_info: dict[str, Any]) -> None:
    """Verify positive fixtures trigger expected risk rules (100% recall)."""
    fixture_dir = Path(__file__).resolve().parent.parent / "fixtures" / "detectors"
    diff_file = fixture_dir / fixture_info["name"]
    assert diff_file.is_file()

    diff_text = diff_file.read_text(encoding="utf-8")
    files = parse_unified_diff(diff_text)
    ingest_result = IngestResult(files=files, raw_diff=diff_text, source=fixture_info["name"])

    findings = detect_risks(ingest_result)
    expected_rule = fixture_info["rule_id"]
    expected_concept = fixture_info["concept_id"]

    matching_findings = [f for f in findings if f.rule_id == expected_rule]
    assert len(matching_findings) >= fixture_info["expected_count"], (
        f"Fixture {fixture_info['name']} failed to trigger rule {expected_rule}. "
        f"Findings returned: {[(f.rule_id, f.title) for f in findings]}"
    )

    finding = matching_findings[0]
    assert finding.concept_id == expected_concept
    assert finding.snippet != ""
    assert finding.title != ""
    assert finding.severity.value in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")


@pytest.mark.parametrize(
    "fixture_info", NEGATIVE_FIXTURES, ids=[f["name"] for f in NEGATIVE_FIXTURES]
)
def test_negative_detector_fixtures(fixture_info: dict[str, Any]) -> None:
    """Verify negative fixtures do NOT trigger false positives (100% precision)."""
    fixture_dir = Path(__file__).resolve().parent.parent / "fixtures" / "detectors"
    diff_file = fixture_dir / fixture_info["name"]
    assert diff_file.is_file()

    diff_text = diff_file.read_text(encoding="utf-8")
    files = parse_unified_diff(diff_text)
    ingest_result = IngestResult(files=files, raw_diff=diff_text, source=fixture_info["name"])

    findings = detect_risks(ingest_result)
    expected_rule = fixture_info["rule_id"]

    matching_findings = [f for f in findings if f.rule_id == expected_rule]
    assert len(matching_findings) == 0, (
        f"False positive on negative fixture {fixture_info['name']} for {expected_rule}: "
        f"{[f.to_dict() for f in matching_findings]}"
    )
