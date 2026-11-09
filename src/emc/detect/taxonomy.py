"""Taxonomy loader and registry for EMC concept mastery tracking."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


class ConceptDefinition(BaseModel):
    """Metadata definition for a mastery taxonomy concept."""

    id: str
    name: str
    category: str
    severity_default: str = "MEDIUM"
    description: str = ""
    remediation: str = ""
    doc_url: str = ""


class TaxonomyRegistry:
    """Registry managing known concept taxonomy definitions."""

    def __init__(self, concepts: list[ConceptDefinition]) -> None:
        self._concepts: dict[str, ConceptDefinition] = {c.id: c for c in concepts}

    def get(self, concept_id: str) -> ConceptDefinition | None:
        """Lookup a concept definition by its identifier."""
        return self._concepts.get(concept_id)

    def contains(self, concept_id: str) -> bool:
        """Check whether a concept identifier exists in taxonomy."""
        return concept_id in self._concepts

    def all_concepts(self) -> list[ConceptDefinition]:
        """Return list of all registered concept definitions."""
        return list(self._concepts.values())

    def validate(self, concept_id: str) -> None:
        """Raise KeyError if concept_id is not in taxonomy."""
        if concept_id not in self._concepts:
            registered = list(self._concepts.keys())
            raise KeyError(f"Unknown concept ID '{concept_id}'. Registered concepts: {registered}")


_GLOBAL_TAXONOMY: TaxonomyRegistry | None = None


def find_concepts_file() -> Path | None:
    """Locate concepts.yaml file from standard repository locations."""
    # 1. Package directory (src/emc/concepts.yaml)
    pkg_file = Path(__file__).resolve().parent.parent / "concepts.yaml"
    if pkg_file.is_file():
        return pkg_file

    # 2. Current working directory
    cwd_file = Path.cwd() / "concepts.yaml"
    if cwd_file.is_file():
        return cwd_file

    # 3. Subdirectory explain-my-own-code/concepts.yaml
    sub_file = Path.cwd() / "explain-my-own-code" / "concepts.yaml"
    if sub_file.is_file():
        return sub_file

    return None


def load_taxonomy(custom_path: Path | None = None) -> TaxonomyRegistry:
    """Load taxonomy definitions from YAML file."""
    path = custom_path or find_concepts_file()
    if not path or not path.is_file():
        # Fallback to minimal built-in concepts if file not found
        return TaxonomyRegistry([])

    try:
        content = path.read_text(encoding="utf-8")
        data: dict[str, Any] = yaml.safe_load(content) or {}
    except Exception:
        return TaxonomyRegistry([])

    concepts_raw = data.get("concepts", [])
    concepts: list[ConceptDefinition] = []
    for item in concepts_raw:
        if isinstance(item, dict) and "id" in item:
            concepts.append(
                ConceptDefinition(
                    id=str(item["id"]),
                    name=str(item.get("name", item["id"])),
                    category=str(item.get("category", "generic")),
                    severity_default=str(item.get("severity_default", "MEDIUM")),
                    description=str(item.get("description", "")),
                    remediation=str(item.get("remediation", "")),
                    doc_url=str(item.get("doc_url", "")),
                )
            )

    return TaxonomyRegistry(concepts)


def get_taxonomy() -> TaxonomyRegistry:
    """Retrieve or initialize the global taxonomy registry."""
    global _GLOBAL_TAXONOMY
    if _GLOBAL_TAXONOMY is None:
        _GLOBAL_TAXONOMY = load_taxonomy()
    return _GLOBAL_TAXONOMY
