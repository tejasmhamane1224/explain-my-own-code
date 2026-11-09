"""Question Planner: Combines targeted templates for detected risks with open hunk analysis."""

from __future__ import annotations

from emc.detect.models import DetectionReport
from emc.questions.schema import QuestionPlan, QuestionType

# Canonical mapping from static detector rule IDs to targeted question types and templates
RULE_STRATEGY_MAP: dict[str, tuple[QuestionType, str, str]] = {
    # Anchor Smart Contract Rules
    "anchor.missing_signer": (
        QuestionType.CONSEQUENCE,
        "What happens to authority or fund security if this account is passed without signing?",
        "Focus on unauthorized state changes, fund theft, or caller spoofing.",
    ),
    "anchor.unchecked_account": (
        QuestionType.CONSEQUENCE,
        (
            "What security risk arises from leaving this account unchecked "
            "without ownership validation?"
        ),
        "Focus on fake account data injection and lack of program owner verification.",
    ),
    "math.unchecked_arith": (
        QuestionType.PREDICT_OUTPUT,
        "What will occur during token calculation if an overflow or underflow state is reached?",
        "Focus on runtime panic in debug mode vs silent integer wrap in release mode.",
    ),
    "anchor.pda_seeds": (
        QuestionType.WHAT_BREAKS_IF,
        "What occurs if a caller provides a non-canonical bump or colliding seeds for this PDA?",
        "Focus on PDA derivation mismatch, frontrunning, or program invocation failure.",
    ),
    "anchor.invoke_signed": (
        QuestionType.CONSEQUENCE,
        (
            "What is the security consequence if the signer seed slice "
            "does not include the canonical bump?"
        ),
        "Focus on invoke_signed authorization failure and signature verification bypass.",
    ),
    "anchor.realloc_close": (
        QuestionType.CONSEQUENCE,
        (
            "What happens to account lamports or data when realloc/close "
            "is performed without zeroing?"
        ),
        "Focus on rent draining, account revival, and residual data reuse.",
    ),
    "anchor.remaining_accounts": (
        QuestionType.WHAT_BREAKS_IF,
        (
            "What vulnerability occurs if remaining_accounts are consumed "
            "without verifying their owner/key?"
        ),
        "Focus on arbitrary account injection and unauthorized multi-account operations.",
    ),
    "anchor.unverified_cpi": (
        QuestionType.CONSEQUENCE,
        "What is the consequence of passing an untyped AccountInfo for the CPI target program?",
        "Focus on malicious target program substitution and theft of approved tokens.",
    ),
    # TypeScript Wallet Rules
    "ts.lamport_units": (
        QuestionType.PREDICT_OUTPUT,
        "What will the resulting balance or transaction amount be given this unit calculation?",
        (
            "Focus on the 10^9 factor difference between 1 SOL and 1 lamport, "
            "or floating point truncation."
        ),
    ),
    "ts.base_units": (
        QuestionType.PREDICT_OUTPUT,
        (
            "What amount will actually be transferred if human token units "
            "are passed without decimal scaling?"
        ),
        "Focus on 1 token vs 1 base unit (e.g. 0.000001 for 6 decimals).",
    ),
    "ts.address_validation": (
        QuestionType.WHAT_BREAKS_IF,
        (
            "What failure occurs if an off-curve address or malformed Base58 "
            "string is passed to this constructor?"
        ),
        (
            "Focus on unhandled exceptions causing client crashes "
            "or unintended program account transfers."
        ),
    ),
    "ts.hardcoded_rpc": (
        QuestionType.WHAT_BREAKS_IF,
        (
            "What breaks if this hardcoded RPC endpoint is rate-limited "
            "or taken offline in production?"
        ),
        "Focus on single point of failure, client transaction drop, and credential exposure.",
    ),
    # Generic Code Smell Rules
    "generic.bypass_flag": (
        QuestionType.SPOT_THE_BUG,
        (
            "Identify the security bypass flag in this snippet "
            "and explain what safety check it disables."
        ),
        "Focus on skipped authentication, disabled type-checking, or unescaped HTML injection.",
    ),
    "generic.sensitive_log": (
        QuestionType.WHAT_BREAKS_IF,
        "What vulnerability is created when this sensitive variable is output to the logs?",
        "Focus on credential exfiltration via log aggregators and third-party monitoring.",
    ),
    "generic.hardcoded_fallback": (
        QuestionType.SPOT_THE_BUG,
        "Identify the insecure fallback credential or default value present in this hunk.",
        "Focus on trivial default keys used in production if the environment variable is unset.",
    ),
    "generic.empty_catch": (
        QuestionType.WHAT_BREAKS_IF,
        "What failure mode occurs when exceptions in this try/catch block are silently discarded?",
        "Focus on hidden failure, corrupt intermediate state, and broken transaction invariants.",
    ),
}


def create_question_plans(
    report: DetectionReport,
    max_questions: int = 5,
) -> list[QuestionPlan]:
    """Generate prioritized QuestionPlans from detection findings and ranked diff hunks."""
    plans: list[QuestionPlan] = []
    seen_files_and_ranges: set[tuple[str, int, int]] = set()

    for ranked_hunk in report.ranked_hunks:
        if len(plans) >= max_questions:
            break

        file_path = ranked_hunk.file_path
        snippet_lines: list[str] = []
        is_deletion = False

        if ranked_hunk.hunk and ranked_hunk.hunk.lines:
            for line_item in ranked_hunk.hunk.lines:
                if line_item.line_type in ("+", " "):
                    snippet_lines.append(line_item.content)
            if not snippet_lines:
                for line_item in ranked_hunk.hunk.lines:
                    if line_item.line_type == "-":
                        snippet_lines.append(line_item.content)
                if snippet_lines:
                    is_deletion = True

        selected_lines = snippet_lines[:15]
        start_line = ranked_hunk.hunk.old_start if is_deletion else ranked_hunk.hunk.new_start
        end_line = start_line + len(selected_lines) - 1 if selected_lines else start_line

        range_key = (file_path, start_line, end_line)
        if range_key in seen_files_and_ranges:
            continue
        seen_files_and_ranges.add(range_key)

        snippet_text = (
            "\n".join(selected_lines) if selected_lines else f"# {file_path}:{start_line}"
        )
        concept = ranked_hunk.primary_concept or "generic.diff_comprehension"

        # Check if hunk triggered any static detector rules
        if ranked_hunk.triggered_rule_ids:
            primary_rule = ranked_hunk.triggered_rule_ids[0]
            strategy_info = RULE_STRATEGY_MAP.get(primary_rule)
            if strategy_info:
                q_type, stem_tpl, instructions = strategy_info
                plans.append(
                    QuestionPlan(
                        hunk=ranked_hunk,
                        target_concept=concept,
                        recommended_type=q_type,
                        strategy="templated",
                        stem_template=stem_tpl,
                        prompt_instructions=instructions,
                        file_path=file_path,
                        start_line=start_line,
                        end_line=end_line,
                        snippet=snippet_text,
                    )
                )
                continue

        # Open hunk fallback (no specific static rule triggered)
        additions_count = len(ranked_hunk.hunk.added_lines)
        open_type = (
            QuestionType.PREDICT_OUTPUT if additions_count >= 5 else QuestionType.WHAT_BREAKS_IF
        )
        plans.append(
            QuestionPlan(
                hunk=ranked_hunk,
                target_concept=concept,
                recommended_type=open_type,
                strategy="llm_open",
                stem_template=f"What is the intended behavior of the changes in {file_path}?",
                prompt_instructions=(
                    "Ask about side-effects, return values, or edge cases introduced."
                ),
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                snippet=snippet_text,
            )
        )

    return plans
