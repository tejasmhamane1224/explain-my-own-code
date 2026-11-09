"""Unit tests for Question schemas, RubricCriterion, and QualityGate models."""

from __future__ import annotations

from emc.questions.schema import (
    Distractor,
    QualityGateRejection,
    Question,
    QuestionType,
    RubricCriterion,
    ValidationResult,
)


def test_question_types_enum() -> None:
    """Verify all 5 canonical question types are present."""
    types = {q.value for q in QuestionType}
    assert types == {
        "predict-output",
        "what-breaks-if",
        "consequence",
        "spot-the-bug",
        "explain-back",
    }


def test_question_model_serialization_and_get_correct_choice() -> None:
    """Verify Question model serialization, fields, and correct choice retrieval."""
    q = Question(
        type=QuestionType.CONSEQUENCE,
        concept_id="anchor.missing_signer",
        hunk_rank=1,
        file_path="programs/vault/src/lib.rs",
        start_line=10,
        end_line=15,
        snippet="pub struct Withdraw<'info> {\n    pub authority: AccountInfo<'info>,\n}",
        stem="What authority vulnerability occurs if authority is not Signer<'info>?",
        choices=[
            Distractor(key="A", text="Unauthorized callers can drain vault funds"),
            Distractor(key="B", text="Transaction fails during compilation"),
            Distractor(key="C", text="Lamport rent exemption is revoked"),
            Distractor(key="D", text="Solana runtime throws ProgramError::InvalidArgument"),
        ],
        answer_key="A",
        explanation="Without Signer<'info>, anyone can pass the vault authority's public key.",
        hint_ladder=[
            "Check account type of authority.",
            "AccountInfo does not verify signature.",
            "Anyone can sign as caller and supply authority pubkey.",
        ],
    )

    assert q.type == QuestionType.CONSEQUENCE
    correct = q.get_correct_choice()
    assert correct is not None
    assert correct.key == "A"
    assert "drain vault funds" in correct.text

    # Serialization test
    dumped = q.model_dump()
    assert dumped["concept_id"] == "anchor.missing_signer"
    assert len(dumped["choices"]) == 4
    assert len(dumped["hint_ladder"]) == 3


def test_spot_the_bug_mutant_snippet() -> None:
    """Verify spot-the-bug question includes mutant_snippet."""
    q = Question(
        type=QuestionType.SPOT_THE_BUG,
        concept_id="generic.hardcoded_fallback",
        hunk_rank=2,
        file_path="src/config.ts",
        start_line=20,
        end_line=22,
        snippet="const key = process.env.SECRET_KEY;",
        mutant_snippet='const key = process.env.SECRET_KEY || "insecure_default_secret";',
        stem="Identify the security flaw injected into this mutant snippet.",
        choices=[
            Distractor(key="A", text="Hardcoded fallback credential leaks in production"),
            Distractor(key="B", text="Environment variable lookup fails at compile time"),
        ],
        answer_key="A",
        explanation="Fallback credential will be used whenever SECRET_KEY is not defined.",
    )
    assert q.mutant_snippet is not None
    assert "insecure_default_secret" in q.mutant_snippet


def test_explain_back_with_rubric() -> None:
    """Verify explain-back free text question with structured RubricCriterion."""
    q = Question(
        type=QuestionType.EXPLAIN_BACK,
        concept_id="ts.lamport_units",
        hunk_rank=1,
        file_path="src/wallet.ts",
        start_line=5,
        end_line=8,
        snippet="const amountInLamports = amountInSol * LAMPORTS_PER_SOL;",
        stem=(
            "Explain why multiplying by LAMPORTS_PER_SOL is necessary before calling"
            " SystemProgram.transfer."
        ),
        answer_key=(
            "SOL units must be converted to base lamports (10^9) before constructing"
            " the on-chain instruction."
        ),
        explanation="SystemProgram accepts balance integers in lamports, not floating-point SOL.",
        rubric=[
            RubricCriterion(
                name="Base unit distinction",
                description="Mentions SystemProgram transfer operates in lamports (10^9) not SOL",
                points=2,
                required_concepts=["ts.lamport_units"],
            ),
            RubricCriterion(
                name="Floating point risk",
                description="Notes potential float precision loss if big numbers are involved",
                points=1,
            ),
        ],
    )
    assert len(q.rubric) == 2
    assert q.rubric[0].points == 2


def test_validation_result_and_rejection_models() -> None:
    """Verify QualityGateRejection and ValidationResult behaviors."""
    rej1 = QualityGateRejection(
        step="snippet_grounding",
        reason="Snippet does not match diff",
        details={"line": 12},
    )
    rej2 = QualityGateRejection(
        step="no_answer_leak",
        reason="Answer leaked in stem",
    )
    vr = ValidationResult(passed=False, rejections=[rej1, rej2], attempts=2)
    assert vr.passed is False
    assert vr.primary_rejection == rej1
    assert len(vr.rejections) == 2

    vr_pass = ValidationResult(passed=True, rejections=[])
    assert vr_pass.passed is True
    assert vr_pass.primary_rejection is None
