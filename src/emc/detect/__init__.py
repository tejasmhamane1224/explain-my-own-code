"""Deterministic static risk detectors and hunk ranking engine."""

from __future__ import annotations

from emc.detect.engine import detect_file_risks, detect_risks, run_detector_pipeline
from emc.detect.models import DetectionFinding, DetectionReport, RankedHunk, RiskSeverity
from emc.detect.ranking import compute_file_multiplier, rank_hunks
from emc.detect.taxonomy import ConceptDefinition, TaxonomyRegistry, get_taxonomy, load_taxonomy

__all__ = [
    "ConceptDefinition",
    "DetectionFinding",
    "DetectionReport",
    "RankedHunk",
    "RiskSeverity",
    "TaxonomyRegistry",
    "compute_file_multiplier",
    "detect_file_risks",
    "detect_risks",
    "get_taxonomy",
    "load_taxonomy",
    "rank_hunks",
    "run_detector_pipeline",
]
