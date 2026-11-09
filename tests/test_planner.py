"""Unit tests for question planning logic."""

from __future__ import annotations

from emc.detect import run_detector_pipeline
from emc.ingest import IngestResult, parse_unified_diff
from emc.plan import create_question_plans
from emc.questions.schema import QuestionType


def test_planner_anchor_missing_signer_generates_consequence_plan() -> None:
    """Verify missing signer Anchor finding maps to consequence question plan."""
    diff_text = (
        "diff --git a/programs/vault/src/lib.rs b/programs/vault/src/lib.rs\n"
        "--- a/programs/vault/src/lib.rs\n"
        "+++ b/programs/vault/src/lib.rs\n"
        "@@ -10,3 +10,4 @@\n"
        "+#[derive(Accounts)]\n"
        "+pub struct Withdraw<'info> {\n"
        "+    pub authority: AccountInfo<'info>,\n"
        "+}\n"
    )
    ingest_result = IngestResult(files=parse_unified_diff(diff_text), raw_diff=diff_text)
    report = run_detector_pipeline(ingest_result)

    plans = create_question_plans(report, max_questions=3)
    assert len(plans) >= 1
    top_plan = plans[0]
    assert top_plan.target_concept == "anchor.signer_check"
    assert top_plan.recommended_type == QuestionType.CONSEQUENCE
    assert top_plan.is_templated is True
    assert top_plan.start_line == 10
    assert "authority: AccountInfo" in top_plan.snippet


def test_planner_ts_lamport_units_generates_predict_output_plan() -> None:
    """Verify ts.lamport_units rule maps to predict-output question plan."""
    diff_text = (
        "diff --git a/src/wallet.ts b/src/wallet.ts\n"
        "--- a/src/wallet.ts\n"
        "+++ b/src/wallet.ts\n"
        "@@ -25,2 +25,3 @@\n"
        "+const transferAmount = balance + solAmount;\n"
        "+console.log(transferAmount);\n"
    )
    ingest_result = IngestResult(files=parse_unified_diff(diff_text), raw_diff=diff_text)
    report = run_detector_pipeline(ingest_result)

    plans = create_question_plans(report, max_questions=2)
    assert len(plans) >= 1
    assert plans[0].target_concept == "ts.lamport_units"
    assert plans[0].recommended_type == QuestionType.PREDICT_OUTPUT
    assert plans[0].is_templated is True


def test_planner_open_hunk_strategy() -> None:
    """Verify hunks without static risk triggers use llm_open strategy."""
    diff_text = (
        "diff --git a/src/utils.py b/src/utils.py\n"
        "--- a/src/utils.py\n"
        "+++ b/src/utils.py\n"
        "@@ -1,4 +1,12 @@\n"
        "+def format_user_display(name: str, handle: str) -> str:\n"
        "+    cleaned_name = name.strip()\n"
        "+    cleaned_handle = handle.lower().lstrip('@')\n"
        "+    return f'{cleaned_name} (@{cleaned_handle})'\n"
        "+\n"
        "+def sanitize_slug(text: str) -> str:\n"
        "+    return text.replace(' ', '-').lower()\n"
    )
    ingest_result = IngestResult(files=parse_unified_diff(diff_text), raw_diff=diff_text)
    report = run_detector_pipeline(ingest_result)

    plans = create_question_plans(report, max_questions=1)
    assert len(plans) == 1
    plan = plans[0]
    assert plan.strategy == "llm_open"
    assert plan.is_templated is False
    assert plan.recommended_type == QuestionType.PREDICT_OUTPUT
