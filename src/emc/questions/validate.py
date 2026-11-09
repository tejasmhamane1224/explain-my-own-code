"""4-Step Question Quality Gate: Grounding, No Leakage, Solvability, and Injection Defense."""

from __future__ import annotations

import re
from typing import Any

from emc.ingest import IngestResult, encapsulate_diff
from emc.llm.base import LLMProvider
from emc.questions.schema import (
    AmbiguityEvaluation,
    QualityGateRejection,
    Question,
    QuestionType,
    SolverSolution,
    ValidationResult,
)

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(
        r"disregard\s+(?:all\s+)?(?:prior|previous)\s+(?:prompts?|instructions?)",
        re.IGNORECASE,
    ),
    re.compile(r"system\s+(?:override|prompt)", re.IGNORECASE),
    re.compile(r"developer\s+mode", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"dan\s+mode", re.IGNORECASE),
    re.compile(r"unrestricted\s+mode", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:in|an?)", re.IGNORECASE),
    re.compile(r"new\s+system\s+(?:prompt|instructions?)", re.IGNORECASE),
    re.compile(r"<<<UNTRUSTED_DIFF", re.IGNORECASE),
    re.compile(r"<<<END_UNTRUSTED_DIFF", re.IGNORECASE),
    re.compile(r"</(?:untrusted_diff|untrusted_input|diff|system)>", re.IGNORECASE),
    re.compile(r"bypass\s+(?:security|comprehension|quiz|check)", re.IGNORECASE),
    re.compile(r"always\s+answer\s+true", re.IGNORECASE),
    re.compile(r"mark\s+(?:all\s+)?as\s+(?:pass|correct)", re.IGNORECASE),
    re.compile(r"score\s*:\s*100", re.IGNORECASE),
    re.compile(r'"comprehension_passed"\s*:\s*true', re.IGNORECASE),
]

URL_PATTERN = re.compile(r"https?://[^\s)\]>\"']+")


class QuestionValidator:
    """Validates candidate comprehension questions against the 4-step quality gate."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider

    def _extract_diff_text(self, diff: IngestResult | str | list[Any]) -> str:
        """Helper to get raw string representation of diff."""
        if isinstance(diff, IngestResult):
            return diff.raw_diff
        if isinstance(diff, list):
            return "\n".join(getattr(f, "raw", str(f)) for f in diff)
        return str(diff)

    def validate_snippet_grounding(
        self,
        question: Question,
        diff: IngestResult | str | list[Any],
    ) -> QualityGateRejection | None:
        """Step 1: Check that quoted snippet and line range exist verbatim in the diff."""
        if isinstance(diff, list):
            diff = IngestResult(files=diff, raw_diff=self._extract_diff_text(diff))

        raw_diff = self._extract_diff_text(diff)
        target_path = question.file_path.replace("\\", "/").lstrip("/")

        # Check line numbering sanity
        if question.start_line > question.end_line:
            return QualityGateRejection(
                step="snippet_grounding",
                reason=(
                    f"Invalid line range: start_line ({question.start_line}) "
                    f"> end_line ({question.end_line})"
                ),
                details={"start_line": question.start_line, "end_line": question.end_line},
            )

        snippet_lines = [line.strip() for line in question.snippet.splitlines() if line.strip()]
        if not snippet_lines:
            return QualityGateRejection(
                step="snippet_grounding",
                reason="Question snippet is empty or contains only whitespace",
                details={"snippet": question.snippet},
            )

        # Check if file exists in diff
        if isinstance(diff, IngestResult):
            matching_files = [
                f
                for f in diff.files
                if (f.new_path and f.new_path.replace("\\", "/").lstrip("/") == target_path)
                or (f.old_path and f.old_path.replace("\\", "/").lstrip("/") == target_path)
            ]
            if not matching_files:
                return QualityGateRejection(
                    step="snippet_grounding",
                    reason=f"Target file '{question.file_path}' does not exist in the diff",
                    details={"file_path": question.file_path},
                )
            target_file = matching_files[0]

            # Check that all snippet lines exist somewhere in the file hunks
            all_file_lines: list[str] = [
                line.content.strip()
                for hunk in target_file.hunks
                for line in hunk.lines
                if line.content.strip()
            ]
            combined_file_text = "\n".join(all_file_lines)
            if not all(s in combined_file_text for s in snippet_lines):
                return QualityGateRejection(
                    step="snippet_grounding",
                    reason=(
                        f"Snippet text does not exist verbatim in diff for '{question.file_path}'"
                    ),
                    details={"file_path": question.file_path, "snippet": question.snippet},
                )

            # Check if any single hunk contains the full contiguous line range
            expected_range_set = set(range(question.start_line, question.end_line + 1))
            candidate_hunks_with_lines: list[list[str]] = []

            for hunk in target_file.hunks:
                # Option A: Check post-image new line numbers (for added and context lines)
                present_new = {
                    line_item.new_line_number
                    for line_item in hunk.lines
                    if line_item.new_line_number is not None
                    and question.start_line <= line_item.new_line_number <= question.end_line
                }
                if expected_range_set.issubset(present_new):
                    new_lines_in_range = [
                        line_item.content.strip()
                        for line_item in hunk.lines
                        if line_item.new_line_number is not None
                        and question.start_line <= line_item.new_line_number <= question.end_line
                        and line_item.content.strip()
                    ]
                    candidate_hunks_with_lines.append(new_lines_in_range)
                    continue

                # Option B: Check pre-image old line numbers (for deleted lines)
                present_old = {
                    line_item.old_line_number
                    for line_item in hunk.lines
                    if line_item.old_line_number is not None
                    and question.start_line <= line_item.old_line_number <= question.end_line
                }
                if expected_range_set.issubset(present_old):
                    old_lines_in_range = [
                        line_item.content.strip()
                        for line_item in hunk.lines
                        if line_item.old_line_number is not None
                        and question.start_line <= line_item.old_line_number <= question.end_line
                        and line_item.content.strip()
                    ]
                    candidate_hunks_with_lines.append(old_lines_in_range)

            if not candidate_hunks_with_lines:
                return QualityGateRejection(
                    step="snippet_grounding",
                    reason=(
                        f"Specified line range {question.start_line}-{question.end_line} "
                        f"does not exist in diff for '{question.file_path}'"
                    ),
                    details={
                        "file_path": question.file_path,
                        "start_line": question.start_line,
                        "end_line": question.end_line,
                    },
                )

            range_matches = False
            for hunk_range_lines in candidate_hunks_with_lines:
                if len(snippet_lines) <= len(hunk_range_lines):
                    for i in range(len(hunk_range_lines) - len(snippet_lines) + 1):
                        window = hunk_range_lines[i : i + len(snippet_lines)]
                        if all(s == w or s in w or w in s for s, w in zip(snippet_lines, window)):
                            range_matches = True
                            break
                if range_matches:
                    break

            if not range_matches:
                return QualityGateRejection(
                    step="snippet_grounding",
                    reason=(
                        f"Snippet text does not match specified line range "
                        f"{question.start_line}-{question.end_line} in {question.file_path}"
                    ),
                    details={
                        "file_path": question.file_path,
                        "start_line": question.start_line,
                        "end_line": question.end_line,
                        "snippet": question.snippet,
                    },
                )

        else:
            # Fallback raw diff string check
            if target_path not in raw_diff.replace("\\", "/"):
                return QualityGateRejection(
                    step="snippet_grounding",
                    reason=f"Target file '{question.file_path}' not found in raw diff",
                    details={"file_path": question.file_path},
                )
            if not all(ln in raw_diff for ln in snippet_lines):
                return QualityGateRejection(
                    step="snippet_grounding",
                    reason="Snippet text not found verbatim in diff",
                    details={"snippet": question.snippet},
                )

        return None

    def validate_no_answer_leakage(self, question: Question) -> QualityGateRejection | None:
        """Step 2: Check that answer key or correct text is not leaked in question."""
        target_key = question.answer_key.strip().upper()
        correct_choice = question.get_correct_choice()
        correct_text = (
            correct_choice.text.strip() if correct_choice else question.answer_key.strip()
        )

        stem = question.stem.strip()
        stem_lower = stem.lower()

        # 1. Check for explicit answer key statements in stem
        key_patterns = [
            rf"\b(?:the\s+)?(?:correct\s+)?answer\s+(?:is|=)\s*\(?({target_key})\)?\b",
            rf"\boption\s+\(?({target_key})\)?\s+(?:is\s+)?(?:the\s+)?(?:correct|answer|right)\b",
            rf"\bchoice\s+\(?({target_key})\)?\s+(?:is\s+)?(?:the\s+)?(?:correct|answer|right)\b",
            rf"\b\(?({target_key})\)?\s+is\s+(?:the\s+)?(?:correct|answer|right)\b",
            rf"\bwhy\s+is\s+(?:option\s+|choice\s+)?\(?({target_key})\)?\b",
            rf"\bsee\s+(?:option\s+|choice\s+)?\(?({target_key})\)?\s+for\b",
            rf"\bunlike\s+\(?({target_key})\)?\b",
        ]
        for pat in key_patterns:
            m = re.search(pat, stem, re.IGNORECASE)
            if m:
                return QualityGateRejection(
                    step="no_answer_leak",
                    reason=(
                        f"Question stem explicitly reveals that option '{target_key}' is correct"
                    ),
                    details={"stem": stem, "leaked_key": target_key},
                )

        # 2. Check for verbatim leak of correct answer text in the stem (for substantive phrases)
        if len(correct_text) >= 8:
            if correct_text.lower() in stem_lower:
                return QualityGateRejection(
                    step="no_answer_leak",
                    reason="Question stem contains the verbatim text of the correct answer",
                    details={"stem": stem, "leaked_text": correct_text},
                )

        # 3. Check for answer leakage in other distractors
        for choice in question.choices:
            if choice.key.strip().upper() != target_key:
                choice_text = choice.text.strip()
                choice_exp = choice.explanation.strip()

                # Check if distractor text or explanation reveals target key
                for pat in key_patterns:
                    if re.search(pat, choice_text, re.IGNORECASE) or re.search(
                        pat, choice_exp, re.IGNORECASE
                    ):
                        return QualityGateRejection(
                            step="no_answer_leak",
                            reason=(
                                f"Distractor '{choice.key}' reveals that choice "
                                f"'{target_key}' is correct"
                            ),
                            details={"choice_key": choice.key, "target_key": target_key},
                        )

                # Check if distractor leaks substantive correct answer text
                if len(correct_text) >= 8 and (
                    correct_text.lower() in choice_text.lower()
                    or correct_text.lower() in choice_exp.lower()
                ):
                    return QualityGateRejection(
                        step="no_answer_leak",
                        reason=(f"Distractor '{choice.key}' leaks the correct answer text"),
                        details={"choice_key": choice.key, "leaked_text": correct_text},
                    )

        return None

    def validate_independent_solvability(
        self,
        question: Question,
        diff: IngestResult | str,
        provider: LLMProvider | None = None,
    ) -> QualityGateRejection | None:
        """Step 3: Independent solver pass given only the diff must reproduce answer key."""
        active_provider = provider or self.provider
        if active_provider is None:
            # Without provider, cannot run LLM solver pass
            return None

        # Free-text explain-back questions are rubric-judged, not multiple choice
        if question.type == QuestionType.EXPLAIN_BACK or not question.choices:
            return None

        raw_diff = self._extract_diff_text(diff)
        safe_diff = encapsulate_diff(raw_diff)
        choices_text = "\n".join(f"{c.key}) {c.text}" for c in question.choices)

        mutant_section = ""
        if question.mutant_snippet:
            mutant_section = (
                f"\nMUTANT SNIPPET (CONTAINING INJECTED BUG):\n"
                f"```\n{question.mutant_snippet}\n```\n"
            )

        solver_prompt = (
            f"You are an independent automated code reviewer. Solve the following question "
            f"strictly based on the provided code diff and context alone. Do not guess.\n\n"
            f"CODE DIFF:\n{safe_diff}\n"
            f"{mutant_section}\n"
            f"QUESTION:\n{question.stem}\n\n"
            f"CHOICES:\n{choices_text}\n\n"
            f"Select the single correct choice key (e.g. A, B, C, D) and explain your reasoning."
        )

        try:
            res = active_provider.generate_structured(
                prompt=solver_prompt,
                schema=SolverSolution,
                system="You are an expert compiler and smart contract security auditor.",
            )
            solver_solution: SolverSolution = res.structured  # type: ignore[assignment]
        except Exception as exc:
            return QualityGateRejection(
                step="independent_solvability",
                reason=f"Independent solver failed to produce a valid solution: {exc}",
                details={"error": str(exc)},
            )

        solver_key = solver_solution.selected_key.strip().upper()
        target_key = question.answer_key.strip().upper()

        if solver_key != target_key:
            return QualityGateRejection(
                step="independent_solvability",
                reason=(
                    f"Independent solver selected choice '{solver_key}', which does not "
                    f"match the expected answer key '{target_key}'"
                ),
                details={
                    "expected_key": target_key,
                    "solver_key": solver_key,
                    "solver_reasoning": solver_solution.reasoning,
                },
            )

        return None

    def validate_non_ambiguity(
        self,
        question: Question,
        diff: IngestResult | str,
        provider: LLMProvider | None = None,
    ) -> QualityGateRejection | None:
        """Step 4: Ambiguity pass flags if multiple defensible answers exist."""
        active_provider = provider or self.provider
        if active_provider is None:
            return None

        if question.type == QuestionType.EXPLAIN_BACK or not question.choices:
            return None

        raw_diff = self._extract_diff_text(diff)
        safe_diff = encapsulate_diff(raw_diff)
        choices_text = "\n".join(f"{c.key}) {c.text}" for c in question.choices)

        mutant_section = ""
        if question.mutant_snippet:
            mutant_section = (
                f"\nMUTANT SNIPPET (CONTAINING INJECTED BUG):\n"
                f"```\n{question.mutant_snippet}\n```\n"
            )

        ambiguity_prompt = (
            f"Analyze the following comprehension question and code diff for ambiguity.\n\n"
            f"CODE DIFF:\n{safe_diff}\n"
            f"{mutant_section}\n"
            f"QUESTION:\n{question.stem}\n\n"
            f"CHOICES:\n{choices_text}\n\n"
            f"INTENDED ANSWER: {question.answer_key}\n\n"
            f"Determine whether any other choices besides '{question.answer_key}' could "
            f"defensibly be argued as correct or valid given the diff alone."
        )

        try:
            res = active_provider.generate_structured(
                prompt=ambiguity_prompt,
                schema=AmbiguityEvaluation,
                system="You are a rigorous psychometrics and testing specialist.",
            )
            ambiguity: AmbiguityEvaluation = res.structured  # type: ignore[assignment]
        except Exception as exc:
            return QualityGateRejection(
                step="non_ambiguity",
                reason=f"Ambiguity evaluation failed: {exc}",
                details={"error": str(exc)},
            )

        if ambiguity.is_ambiguous or len(ambiguity.defensible_choices) > 1:
            return QualityGateRejection(
                step="non_ambiguity",
                reason=(
                    f"Question is ambiguous: multiple defensible choices identified "
                    f"({ambiguity.defensible_choices})"
                ),
                details={
                    "is_ambiguous": ambiguity.is_ambiguous,
                    "defensible_choices": ambiguity.defensible_choices,
                    "reasoning": ambiguity.reasoning,
                },
            )

        return None

    def validate_no_injection_or_instructions(
        self,
        question: Question,
        diff: IngestResult | str,
    ) -> QualityGateRejection | None:
        """Step 5: Reject outputs containing instructions, URLs, or code not present in diff."""
        raw_diff = self._extract_diff_text(diff)

        # Collect all text in the question
        text_corpus = [
            question.stem,
            question.snippet,
            question.explanation,
            *(c.text for c in question.choices),
            *(c.explanation for c in question.choices),
            *(h for h in question.hint_ladder),
            *(r.description for r in question.rubric),
        ]
        if question.mutant_snippet:
            text_corpus.append(question.mutant_snippet)

        combined_text = "\n".join(text_corpus)

        # 1. Check for prompt injection markers
        for pat in INJECTION_PATTERNS:
            match = pat.search(combined_text)
            if match:
                return QualityGateRejection(
                    step="injection_instruction",
                    reason=(
                        f"Question output contains injection instruction pattern: "
                        f"'{match.group(0)}'"
                    ),
                    details={"matched_text": match.group(0)},
                )

        # 2. Check for external URLs not present in the diff
        urls_in_question = URL_PATTERN.findall(combined_text)
        for url in urls_in_question:
            if url not in raw_diff:
                return QualityGateRejection(
                    step="injection_instruction",
                    reason=f"Question introduces external URL '{url}' not present in diff",
                    details={"url": url},
                )

        return None

    def validate(
        self,
        question: Question,
        diff: IngestResult | str,
        provider: LLMProvider | None = None,
    ) -> ValidationResult:
        """Execute all quality gate checks in sequence, returning ValidationResult."""
        rejections: list[QualityGateRejection] = []

        # 0. Structural / schema checks
        if question.type == QuestionType.SPOT_THE_BUG and not question.mutant_snippet:
            return ValidationResult(
                passed=False,
                rejections=[
                    QualityGateRejection(
                        step="schema_violation",
                        reason=(
                            "Spot-the-bug question requires mutant_snippet containing "
                            "the injected flaw"
                        ),
                    )
                ],
            )
        if question.choices and not question.get_correct_choice():
            return ValidationResult(
                passed=False,
                rejections=[
                    QualityGateRejection(
                        step="schema_violation",
                        reason=(
                            f"Answer key '{question.answer_key}' does not match any choice key "
                            f"in {[c.key for c in question.choices]}"
                        ),
                    )
                ],
            )

        # 1. Snippet grounding
        r1 = self.validate_snippet_grounding(question, diff)
        if r1:
            rejections.append(r1)

        # 2. No answer leak
        r2 = self.validate_no_answer_leakage(question)
        if r2:
            rejections.append(r2)

        # 3. Injection / instruction rejection
        r3 = self.validate_no_injection_or_instructions(question, diff)
        if r3:
            rejections.append(r3)

        # If static/deterministic checks failed, fail-fast to save tokens & LLM calls
        if rejections:
            return ValidationResult(passed=False, rejections=rejections)

        # 4. Independent solvability (requires provider)
        r4 = self.validate_independent_solvability(question, diff, provider)
        if r4:
            rejections.append(r4)

        # 5. Non-ambiguity (requires provider)
        r5 = self.validate_non_ambiguity(question, diff, provider)
        if r5:
            rejections.append(r5)

        return ValidationResult(
            passed=len(rejections) == 0,
            rejections=rejections,
        )
