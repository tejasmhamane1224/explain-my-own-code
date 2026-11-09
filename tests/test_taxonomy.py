"""Tests for taxonomy registry and concept definitions."""

from __future__ import annotations

import pytest

from emc.detect.taxonomy import ConceptDefinition, TaxonomyRegistry, get_taxonomy


def test_taxonomy_loads_and_retrieves_concepts() -> None:
    """Verify default taxonomy registry loads concepts from concepts.yaml."""
    taxonomy = get_taxonomy()
    all_concepts = taxonomy.all_concepts()
    assert len(all_concepts) >= 16

    # Verify key concepts exist
    signer = taxonomy.get("anchor.signer_check")
    assert signer is not None
    assert signer.category == "rust_anchor"
    assert signer.severity_default == "CRITICAL"
    assert "Signer<'info>" in signer.remediation

    lamports = taxonomy.get("ts.lamport_units")
    assert lamports is not None
    assert lamports.category == "ts_wallet"

    bypass = taxonomy.get("generic.bypass_flags")
    assert bypass is not None
    assert bypass.category == "generic"


def test_taxonomy_validate_missing_concept_raises() -> None:
    """Verify validate() raises KeyError on invalid concept identifier."""
    taxonomy = get_taxonomy()
    assert taxonomy.contains("anchor.signer_check")
    assert not taxonomy.contains("non_existent.concept_123")

    with pytest.raises(KeyError, match="Unknown concept ID"):
        taxonomy.validate("non_existent.concept_123")


def test_custom_taxonomy_registry() -> None:
    """Verify custom TaxonomyRegistry instance behavior."""
    custom = TaxonomyRegistry(
        [
            ConceptDefinition(
                id="custom.test",
                name="Custom Test Concept",
                category="test",
                severity_default="LOW",
            )
        ]
    )
    assert custom.contains("custom.test")
    assert not custom.contains("anchor.signer_check")
    assert custom.get("custom.test") is not None
