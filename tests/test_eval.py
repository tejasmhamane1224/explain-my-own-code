"""Acceptance tests for Stage 7: Benchmark evaluation suite, mutation generator, and ablation."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from emc.cli import app
from emc.detect import run_detector_pipeline
from emc.eval import (
    EvalReport,
    EvalRunner,
    MutationGenerator,
)
from emc.grade.rubric import grade_rubric
from emc.ingest import ingest_diff
from emc.questions.schema import Question, QuestionType, RubricCriterion


def test_mutation_generator_produces_valid_diffs() -> None:
    """Verify MutationGenerator produces valid unified diffs detected by static rules."""
    generator = MutationGenerator()
    available = generator.available_mutations()
    assert len(available) >= 11, f"Expected at least 11 registered mutations, got {len(available)}"

    mutations = generator.generate_all_mutations()
    assert len(mutations) >= 11

    for mut in mutations:
        assert mut.diff.startswith("diff --git a/")
        assert "--- a/" in mut.diff
        assert "+++ b/" in mut.diff

        # Ingest and parse mutated diff
        ingest_res = ingest_diff(stdin_content=mut.diff)
        assert not ingest_res.is_empty, f"Mutant diff for {mut.mutation_id} parsed as empty"
        assert len(ingest_res.files) == 1

        # Detector pipeline must detect the injected vulnerability
        report = run_detector_pipeline(ingest_res)
        found_rules = [f.rule_id for f in report.findings]
        assert mut.rule_id in found_rules, (
            f"Mutant {mut.mutation_id} did not trigger expected rule {mut.rule_id}. "
            f"Found rules: {found_rules}"
        )


def test_seeded_diffs_load_and_parse_cleanly() -> None:
    """Verify all 30+ benchmark diffs exist, parse cleanly, and trigger expected rules."""
    fixtures_dir = Path(__file__).resolve().parent.parent / "fixtures" / "eval"
    manifest_path = fixtures_dir / "manifest.json"
    assert manifest_path.exists(), f"Missing manifest at {manifest_path}"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    fixtures = manifest["fixtures"]
    assert len(fixtures) >= 30, f"Expected at least 30 seeded bug diffs, found {len(fixtures)}"

    anchor_count = sum(1 for m in fixtures if m["language"] == "rust")
    ts_count = sum(1 for m in fixtures if m["language"] == "typescript")
    assert anchor_count >= 20, f"Expected ~20 Anchor diffs, found {anchor_count}"
    assert ts_count >= 10, f"Expected ~10 TS diffs, found {ts_count}"

    for entry in fixtures:
        filename = entry["filename"]
        diff_file = fixtures_dir / filename
        assert diff_file.exists(), f"Benchmark diff file {diff_file} is missing"

        diff_content = diff_file.read_text(encoding="utf-8")
        assert len(diff_content.strip()) > 0

        # Ingest diff
        ingest_res = ingest_diff(stdin_content=diff_content)
        assert not ingest_res.is_empty, f"Diff {filename} parsed as empty"
        assert len(ingest_res.files) >= 1

        # Detector validation
        report = run_detector_pipeline(ingest_res)
        found_rules = [f.rule_id for f in report.findings]
        assert entry["rule_id"] in found_rules, (
            f"Diff {filename} failed to trigger {entry['rule_id']}. Found: {found_rules}"
        )


def test_free_text_rubric_grader_agreement() -> None:
    """Verify exactly 30 hand-labeled answers evaluate with >=90% agreement metrics."""
    fixtures_dir = Path(__file__).resolve().parent.parent / "fixtures" / "eval"
    rubric_path = fixtures_dir / "free_text_rubric.json"
    assert rubric_path.exists(), f"Missing rubric dataset at {rubric_path}"

    with open(rubric_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    assert len(dataset) == 30, f"Expected exactly 30 hand-labeled answers, got {len(dataset)}"

    matches = 0
    tp = 0
    fp = 0
    tn = 0
    fn = 0

    for item in dataset:
        q_dict = item["question"]
        q = Question(
            id=q_dict["id"],
            type=QuestionType(q_dict["type"]),
            concept_id=q_dict["concept_id"],
            file_path=q_dict["file_path"],
            start_line=q_dict["start_line"],
            end_line=q_dict["end_line"],
            snippet=q_dict["snippet"],
            stem=q_dict["stem"],
            choices=[],
            answer_key="",
            explanation=q_dict["explanation"],
            rubric=[RubricCriterion(**c) for c in q_dict["rubric"]],
        )

        grade_res = grade_rubric(question=q, user_answer=item["developer_answer"], provider=None)
        pred_passed = grade_res.is_correct
        truth_passed = item["ground_truth_passed"]

        if pred_passed == truth_passed:
            matches += 1

        if pred_passed and truth_passed:
            tp += 1
        elif pred_passed and not truth_passed:
            fp += 1
        elif not pred_passed and not truth_passed:
            tn += 1
        else:
            fn += 1

        # Explicitly verify prompt injections are blocked
        if (
            "ignore" in item["developer_answer"].lower()
            or "override" in item["developer_answer"].lower()
        ):
            assert not pred_passed, (
                f"Adversarial prompt injection succeeded on sample {item['id']}!"
            )

    accuracy = (matches / len(dataset)) * 100.0
    precision = (tp / (tp + fp) * 100.0) if (tp + fp) > 0 else 0.0
    recall = (tp / (tp + fn) * 100.0) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    assert accuracy >= 90.0, f"Grader accuracy {accuracy:.1f}% below 90.0% threshold"
    assert precision >= 90.0, f"Grader precision {precision:.1f}% below 90.0% threshold"
    assert recall >= 90.0, f"Grader recall {recall:.1f}% below 90.0% threshold"
    assert f1 >= 90.0, f"Grader F1 {f1:.1f}% below 90.0% threshold"


def test_eval_runner_full_benchmark() -> None:
    """Verify EvalRunner computes all required evaluation metrics and ablation."""
    runner = EvalRunner()
    report: EvalReport = runner.run_benchmark(include_ablation=True)

    assert report.total_seeded_diffs >= 30
    assert report.anchor_diffs_count >= 20
    assert report.ts_diffs_count >= 10
    assert report.seeded_bug_surfacing_rate == 100.0
    assert report.grounded_question_rate == 100.0
    assert report.redaction_recall == 100.0
    assert report.injection_resistance_rate == 100.0
    assert report.grader_agreement.accuracy >= 90.0
    assert report.cost_per_session_usd < 0.05
    assert report.latency_ms.total_pipeline_ms < 500.0

    # Verify ablation comparison
    assert report.ablation is not None
    ab = report.ablation
    assert ab.pipeline_seeded_bug_surfacing_rate > ab.baseline_seeded_bug_surfacing_rate
    assert ab.pipeline_redaction_recall > ab.baseline_redaction_recall
    assert ab.pipeline_injection_resistance_rate > ab.baseline_injection_resistance_rate
    assert ab.baseline_secrets_leaked > 0
    assert ab.pipeline_secrets_leaked == 0


def test_cli_eval_command_text_and_output(cli_runner: CliRunner, tmp_path: Path) -> None:
    """Verify emc eval produces Rich summary and writes markdown report."""
    output_path = tmp_path / "EVAL.md"
    result = cli_runner.invoke(app, ["eval", "--output", str(output_path)])
    assert result.exit_code == 0
    assert "Headline Evaluation Metrics" in result.stdout
    assert "Seeded-Bug Surfacing Rate" in result.stdout
    assert "Grader Agreement" in result.stdout
    assert output_path.exists()

    md_content = output_path.read_text(encoding="utf-8")
    assert "# EMC Benchmark Evaluation & Ablation Report" in md_content
    assert "Seeded Bug Benchmark Dataset" in md_content


def test_cli_eval_command_json(cli_runner: CliRunner) -> None:
    """Verify emc eval --json outputs machine-readable JSON metrics."""
    result = cli_runner.invoke(app, ["eval", "--json"])
    assert result.exit_code == 0

    data = json.loads(result.stdout)
    assert "total_seeded_diffs" in data
    assert data["total_seeded_diffs"] >= 30
    assert "seeded_bug_surfacing_rate" in data
    assert data["seeded_bug_surfacing_rate"] == 100.0
    assert "grader_agreement" in data
    assert data["grader_agreement"]["accuracy"] >= 90.0
    assert "latency_ms" in data


def test_cli_eval_command_ablation(cli_runner: CliRunner) -> None:
    """Verify emc eval --ablation renders side-by-side comparison table."""
    result = cli_runner.invoke(app, ["eval", "--ablation"])
    assert result.exit_code == 0
    assert "Ablation Study" in result.stdout
    assert "Naive Baseline" in result.stdout
    assert "Pipeline" in result.stdout


def test_cli_eval_command_ablation_json(cli_runner: CliRunner) -> None:
    """Verify emc eval --ablation --json includes ablation comparison in JSON."""
    result = cli_runner.invoke(app, ["eval", "--ablation", "--json"])
    assert result.exit_code == 0

    data = json.loads(result.stdout)
    assert data["ablation"] is not None
    assert "pipeline_seeded_bug_surfacing_rate" in data["ablation"]
    assert "baseline_seeded_bug_surfacing_rate" in data["ablation"]
    assert len(data["ablation"]["comparisons"]) >= 5
