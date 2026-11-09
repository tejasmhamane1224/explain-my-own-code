"""Leitner Box Mastery Tracker for tracking concept retention and progression."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from emc.detect.taxonomy import TaxonomyRegistry, get_taxonomy
from emc.ledger.models import ConceptMastery, LedgerEvent, MasteryLevel, MasterySummary
from emc.ledger.storage import read_events


class MasteryTracker:
    """Tracks per-concept comprehension mastery across 5 Leitner boxes."""

    def __init__(
        self,
        taxonomy: TaxonomyRegistry | None = None,
        demote_to_box_1: bool = True,
    ) -> None:
        self.taxonomy = taxonomy or get_taxonomy()
        self.demote_to_box_1 = demote_to_box_1
        # concept_id -> ConceptMastery
        self._masteries: dict[str, ConceptMastery] = {}
        self._initialize_from_taxonomy()

    def _initialize_from_taxonomy(self) -> None:
        """Initialize all canonical concepts from taxonomy in initial Box 1 state."""
        for concept in self.taxonomy.all_concepts():
            self._masteries[concept.id] = ConceptMastery(
                concept_id=concept.id,
                name=concept.name,
                category=concept.category,
                box=1,
                attempts=0,
                correct_count=0,
                streak=0,
                pass_rate=0.0,
                last_reviewed=None,
                mastery_level=MasteryLevel.WEAK,
            )

    def process_event(self, event: LedgerEvent) -> ConceptMastery:
        """Process a single ledger event, advancing or demoting the concept's Leitner box."""
        concept_id = event.concept_id

        if concept_id not in self._masteries:
            # Fallback for dynamic / untaxonomized concept
            concept_def = self.taxonomy.get(concept_id)
            name = concept_def.name if concept_def else concept_id
            category = concept_def.category if concept_def else "generic"
            self._masteries[concept_id] = ConceptMastery(
                concept_id=concept_id,
                name=name,
                category=category,
                box=1,
                attempts=0,
                correct_count=0,
                streak=0,
                pass_rate=0.0,
                last_reviewed=None,
                mastery_level=MasteryLevel.WEAK,
            )

        cur = self._masteries[concept_id]
        new_attempts = cur.attempts + 1

        if event.is_correct:
            new_correct = cur.correct_count + 1
            new_streak = cur.streak + 1
            # Advance to next box, capped at Box 5
            new_box = min(5, cur.box + 1)
        else:
            new_correct = cur.correct_count
            new_streak = 0
            # Demote back on incorrect answer
            if self.demote_to_box_1:
                new_box = 1
            else:
                new_box = max(1, cur.box - 1)

        new_pass_rate = round((new_correct / new_attempts) * 100.0, 2) if new_attempts > 0 else 0.0
        new_level = MasteryLevel.from_box(new_box)

        updated = ConceptMastery(
            concept_id=concept_id,
            name=cur.name,
            category=cur.category,
            box=new_box,
            attempts=new_attempts,
            correct_count=new_correct,
            streak=new_streak,
            pass_rate=new_pass_rate,
            last_reviewed=event.timestamp,
            mastery_level=new_level,
        )
        self._masteries[concept_id] = updated
        return updated

    def process_events(self, events: list[LedgerEvent]) -> None:
        """Process a sequence of ledger events in chronological order."""
        for ev in events:
            self.process_event(ev)

    def get_mastery(self, concept_id: str) -> ConceptMastery:
        """Retrieve the current mastery record for a specific concept."""
        if concept_id in self._masteries:
            return self._masteries[concept_id]
        concept_def = self.taxonomy.get(concept_id)
        if concept_def:
            m = ConceptMastery(
                concept_id=concept_def.id,
                name=concept_def.name,
                category=concept_def.category,
                box=1,
                attempts=0,
                correct_count=0,
                streak=0,
                pass_rate=0.0,
                last_reviewed=None,
                mastery_level=MasteryLevel.WEAK,
            )
            self._masteries[concept_id] = m
            return m
        raise KeyError(f"Concept '{concept_id}' not found in taxonomy or tracker.")

    def get_all_masteries(
        self,
        sort_by: Literal["box_asc", "box_desc", "attempts_desc", "category"] = "box_asc",
    ) -> list[ConceptMastery]:
        """Return all concept masteries ordered by requested criterion."""
        items = list(self._masteries.values())
        if sort_by == "box_asc":
            # Weakest first (Box 1 -> Box 5), then lowest pass rate, then highest attempts
            return sorted(items, key=lambda m: (m.box, m.pass_rate, -m.attempts, m.concept_id))
        elif sort_by == "box_desc":
            # Highest box first
            return sorted(items, key=lambda m: (-m.box, -m.pass_rate, m.concept_id))
        elif sort_by == "attempts_desc":
            return sorted(items, key=lambda m: (-m.attempts, m.box, m.concept_id))
        elif sort_by == "category":
            return sorted(items, key=lambda m: (m.category, m.concept_id))
        return items

    def get_weak_concepts(
        self,
        max_box: int = 2,
        limit: int | None = None,
        only_attempted: bool = False,
    ) -> list[ConceptMastery]:
        """Retrieve concepts in weak/developing state (Box <= max_box) prioritized for review.

        Prioritizes:
        1. Attempted concepts with failures (Box 1 with attempts > 0, lowest pass rate)
        2. Concepts in Box 2 (Developing)
        3. Unattempted concepts (Box 1 with 0 attempts) if only_attempted is False.
        """
        candidates: list[ConceptMastery] = []
        for m in self._masteries.values():
            if m.box <= max_box:
                if only_attempted and m.attempts == 0:
                    continue
                candidates.append(m)

        # Sort: attempted with lowest pass rate first, then box, then least recently reviewed
        def _sort_key(m: ConceptMastery) -> tuple[int, int, float, str]:
            # Priority 0: attempted Box 1; Priority 1: attempted Box 2;
            # Priority 2: unattempted Box 1
            if m.attempts > 0:
                priority = 0 if m.box == 1 else 1
            else:
                priority = 2
            return (priority, m.box, m.pass_rate, m.last_reviewed or "")

        ranked = sorted(candidates, key=_sort_key)
        if limit is not None:
            return ranked[:limit]
        return ranked

    def summary(self) -> MasterySummary:
        """Compute aggregate mastery statistics across all concepts."""
        total_q = sum(m.attempts for m in self._masteries.values())
        total_c = sum(m.correct_count for m in self._masteries.values())
        acc = round((total_c / total_q) * 100.0, 2) if total_q > 0 else 0.0

        b1 = sum(1 for m in self._masteries.values() if m.box == 1)
        b2 = sum(1 for m in self._masteries.values() if m.box == 2)
        b3 = sum(1 for m in self._masteries.values() if m.box == 3)
        b4 = sum(1 for m in self._masteries.values() if m.box == 4)
        b5 = sum(1 for m in self._masteries.values() if m.box == 5)
        active = sum(1 for m in self._masteries.values() if m.attempts > 0)

        return MasterySummary(
            total_questions=total_q,
            total_correct=total_c,
            accuracy_percent=acc,
            mastered_count=b5,
            proficient_count=b4,
            competent_count=b3,
            developing_count=b2,
            weak_count=b1,
            active_concepts=active,
            total_concepts=len(self._masteries),
        )

    @classmethod
    def from_ledger(
        cls,
        ledger_path: Path | None = None,
        taxonomy: TaxonomyRegistry | None = None,
        demote_to_box_1: bool = True,
    ) -> MasteryTracker:
        """Instantiate tracker and replay all historical events from ledger file."""
        tracker = cls(taxonomy=taxonomy, demote_to_box_1=demote_to_box_1)
        events = read_events(ledger_path=ledger_path)
        tracker.process_events(events)
        return tracker
