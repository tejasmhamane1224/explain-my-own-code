"""Deterministic static detectors for Rust and Anchor smart contract code."""

from __future__ import annotations

import re

from emc.detect.models import DetectionFinding, RiskSeverity
from emc.ingest.models import DiffHunk, FileDiff

RE_SIGNER_ATTR = re.compile(r"\bsigner\b")
RE_HAS_ONE_ATTR = re.compile(r"\bhas_one\s*=")

RE_AUTHORITY_FIELD = re.compile(
    r"^\s*pub\s+(authority|owner|admin|payer|signer|\w+_(?:authority|admin|owner|signer))\s*:\s*(.+?),?$"
)

RE_UNCHECKED_ACCOUNT = re.compile(r"\bUncheckedAccount(?:\s*<.*?>)?\b")
RE_CHECK_DOC = re.compile(r"^\s*///\s*CHECK:\s*(.+)$")
RE_CHECK_STUB = re.compile(
    r"^\s*///\s*CHECK:\s*(?:todo|none|unchecked|temp|bypass|\?+)?\s*$", re.IGNORECASE
)

RE_CHECKED_OR_SATURATING = re.compile(r"\.(?:checked|saturating)_(?:add|sub|mul|div)\b")

RE_BUMP_ATTR = re.compile(r"\bbump\b(?:\s*=\s*(\w+(?:\.\w+)*|\d+))?")
RE_HARDCODED_BUMP = re.compile(r"\bbump\s*=\s*\d+\b")

RE_INVOKE_SIGNED = re.compile(r"\binvoke_signed\s*\(")
RE_REALLOC_PAYER = re.compile(r"\brealloc::payer\s*=")
RE_REALLOC_ZERO = re.compile(r"\brealloc::zero\s*=")
RE_MANUAL_LAMPORTS_ZERO = re.compile(r"\*\*(?:\w+\.)?lamports(?:\.borrow_mut\(\))?\s*=\s*0")

RE_PROGRAM_ACCOUNT_INFO = re.compile(
    r"^\s*pub\s+(\w*(?:program|token_program|system_program))\s*:\s*AccountInfo<'info>"
)


def _is_rust_file(path: str) -> bool:
    """Check if file has Rust extension or is Rust program path."""
    clean = path.lower()
    return clean.endswith(".rs") or "programs/" in clean


def detect_rust_anchor_risks(file_diff: FileDiff) -> list[DetectionFinding]:
    """Analyze a single file diff for Rust and Anchor vulnerabilities."""
    findings: list[DetectionFinding] = []
    if not _is_rust_file(file_diff.path):
        return findings

    for hunk_idx, hunk in enumerate(file_diff.hunks):
        findings.extend(_detect_hunk_anchor_risks(file_diff.path, hunk_idx, hunk))

    return findings


def _detect_hunk_anchor_risks(
    file_path: str, hunk_idx: int, hunk: DiffHunk
) -> list[DetectionFinding]:
    """Scan a hunk for all Anchor and Rust vulnerability rules."""
    findings: list[DetectionFinding] = []
    all_lines = hunk.lines

    for i, line in enumerate(all_lines):
        if line.line_type != "+":
            continue

        raw_line = line.content
        line_num = line.new_line_number

        # 1. UncheckedAccount without proper safety comment
        if RE_UNCHECKED_ACCOUNT.search(raw_line):
            has_valid_check = False
            lookback_idx = i - 1
            while lookback_idx >= 0 and lookback_idx >= i - 4:
                prev_line = all_lines[lookback_idx].content.strip()
                if prev_line.startswith("#["):
                    lookback_idx -= 1
                    continue
                check_match = RE_CHECK_DOC.match(prev_line)
                if check_match:
                    reason = check_match.group(1).strip()
                    if not RE_CHECK_STUB.match(prev_line) and len(reason) >= 8:
                        has_valid_check = True
                    break
                if prev_line.startswith("///"):
                    lookback_idx -= 1
                    continue
                break

            if not has_valid_check:
                findings.append(
                    DetectionFinding(
                        rule_id="anchor.unchecked_account",
                        concept_id="anchor.account_types",
                        category="rust_anchor",
                        severity=RiskSeverity.HIGH,
                        title="UncheckedAccount without Safety Documentation",
                        message=(
                            "UncheckedAccount<'info> bypasses Anchor ownership checks. "
                            "It must have a '/// CHECK: <reason>' doc comment."
                        ),
                        file_path=file_path,
                        line_number=line_num,
                        snippet=raw_line.strip(),
                        recommendation="Add '/// CHECK: <reason>' or use typed Account<'info, T>.",
                        hunk_index=hunk_idx,
                    )
                )

        # 2. Missing Signer / has_one constraint on authority accounts
        auth_match = RE_AUTHORITY_FIELD.match(raw_line)
        if auth_match:
            field_name = auth_match.group(1)
            field_type = auth_match.group(2).strip()

            if (
                field_type.startswith("AccountInfo")
                or field_type.startswith("Account<")
                or field_type.startswith("UncheckedAccount")
            ):
                has_signer_protection = False
                lookback_idx = i - 1
                while lookback_idx >= 0 and lookback_idx >= i - 5:
                    prev_line = all_lines[lookback_idx].content.strip()
                    if prev_line.startswith("#[account"):
                        if RE_SIGNER_ATTR.search(prev_line) or RE_HAS_ONE_ATTR.search(prev_line):
                            has_signer_protection = True
                        break
                    lookback_idx -= 1

                if not has_signer_protection and not field_type.startswith("Signer"):
                    findings.append(
                        DetectionFinding(
                            rule_id="anchor.missing_signer",
                            concept_id="anchor.signer_check",
                            category="rust_anchor",
                            severity=RiskSeverity.CRITICAL,
                            title="Authority Account Missing Signer or has_one Constraint",
                            message=(
                                f"Account field '{field_name}' represents an authority "
                                f"typed as '{field_type}' without Signer enforcement."
                            ),
                            file_path=file_path,
                            line_number=line_num,
                            snippet=raw_line.strip(),
                            recommendation=(
                                f"Change '{field_name}' to Signer<'info> or add #[account(signer)]."
                            ),
                            hunk_index=hunk_idx,
                        )
                    )

        # 3. Unchecked arithmetic on balance/financial variables
        if not raw_line.strip().startswith("//") and not raw_line.strip().startswith("/*"):
            stripped = raw_line.strip()
            if not stripped.startswith("use ") and not stripped.startswith("pub trait"):
                has_checked = bool(RE_CHECKED_OR_SATURATING.search(raw_line))
                if not has_checked:
                    keywords = [
                        "balance",
                        "amount",
                        "lamports",
                        "shares",
                        "supply",
                        "fee",
                        "deposit",
                        "withdrawal",
                        "reward",
                    ]
                    has_fin_var = any(k in raw_line.lower() for k in keywords)
                    has_raw_math = any(
                        op in raw_line
                        for op in [
                            " + ",
                            " - ",
                            " * ",
                            " / ",
                            " += ",
                            " -= ",
                            " *= ",
                            " /= ",
                        ]
                    )
                    is_loop = "for " in raw_line or "while " in raw_line
                    is_size_const = "const " in raw_line and (
                        "SIZE" in raw_line or "LEN" in raw_line
                    )
                    if has_fin_var and has_raw_math and not is_loop and not is_size_const:
                        findings.append(
                            DetectionFinding(
                                rule_id="math.unchecked_arith",
                                concept_id="math.checked_arith",
                                category="rust_anchor",
                                severity=RiskSeverity.HIGH,
                                title="Unchecked Arithmetic on Balance / Financial Variables",
                                message=(
                                    "Raw arithmetic operator (+, -, *, /) used on balance values. "
                                    "Unchecked arithmetic risks overflow or panic."
                                ),
                                file_path=file_path,
                                line_number=line_num,
                                snippet=raw_line.strip(),
                                recommendation=(
                                    "Use .checked_add(), .checked_sub(), or .saturating_add()."
                                ),
                                hunk_index=hunk_idx,
                            )
                        )

        # 4. PDA seeds / bump validation
        if "#[account(" in raw_line and "seeds" in raw_line:
            attr_block = raw_line
            forward_idx = i + 1
            while forward_idx < len(all_lines) and forward_idx <= i + 4:
                nxt = all_lines[forward_idx].content
                attr_block += " " + nxt
                if ")]" in nxt:
                    break
                forward_idx += 1

            if "seeds" in attr_block:
                has_bump = bool(RE_BUMP_ATTR.search(attr_block))
                has_hardcoded_bump = bool(RE_HARDCODED_BUMP.search(attr_block))

                if not has_bump:
                    findings.append(
                        DetectionFinding(
                            rule_id="anchor.pda_seeds",
                            concept_id="anchor.pda_seeds",
                            category="rust_anchor",
                            severity=RiskSeverity.HIGH,
                            title="Missing Bump in PDA Seeds Constraint",
                            message=(
                                "PDA account attribute specifies seeds = [...] but omits bump "
                                "verification, enabling PDA seed spoofing."
                            ),
                            file_path=file_path,
                            line_number=line_num,
                            snippet=raw_line.strip(),
                            recommendation=(
                                "Add 'bump' or 'bump = account.bump' to #[account(...)]."
                            ),
                            hunk_index=hunk_idx,
                        )
                    )
                elif has_hardcoded_bump:
                    findings.append(
                        DetectionFinding(
                            rule_id="anchor.pda_seeds",
                            concept_id="anchor.pda_seeds",
                            category="rust_anchor",
                            severity=RiskSeverity.HIGH,
                            title="Hardcoded Bump Seed in PDA Definition",
                            message=(
                                "Hardcoded bump literal detected in seeds attribute. "
                                "Canonical bump must be derived or validated from state."
                            ),
                            file_path=file_path,
                            line_number=line_num,
                            snippet=raw_line.strip(),
                            recommendation=(
                                "Use 'bump = account.bump' or Anchor's 'bump' attribute."
                            ),
                            hunk_index=hunk_idx,
                        )
                    )

        # 5. invoke_signed with improper seed slices or missing bump
        if RE_INVOKE_SIGNED.search(raw_line):
            call_text = raw_line
            fwd = i + 1
            while fwd < len(all_lines) and fwd <= i + 6:
                call_text += " " + all_lines[fwd].content
                if ");" in all_lines[fwd].content or ")?" in all_lines[fwd].content:
                    break
                fwd += 1

            has_empty_seeds = "&[]" in call_text or "&[&[]]" in call_text
            has_bump_in_seeds = (
                "&[bump" in call_text or "&[vault_bump" in call_text or "&[*bump" in call_text
            )

            if has_empty_seeds or not has_bump_in_seeds:
                findings.append(
                    DetectionFinding(
                        rule_id="anchor.invoke_signed",
                        concept_id="anchor.invoke_signed",
                        category="rust_anchor",
                        severity=RiskSeverity.CRITICAL,
                        title="Improper Signer Seeds in invoke_signed CPI",
                        message=(
                            "invoke_signed called with invalid or un-bumped signer seed slice. "
                            "CPI caller authority cannot be validated without canonical bump."
                        ),
                        file_path=file_path,
                        line_number=line_num,
                        snippet=raw_line.strip(),
                        recommendation=(
                            "Supply canonical seed slice: &[&[SEED, auth.as_ref(), &[bump]]]."
                        ),
                        hunk_index=hunk_idx,
                    )
                )

        # 6. Account realloc / close safety
        if "realloc" in raw_line and "#[account" in raw_line:
            attr_block = raw_line
            fwd = i + 1
            while fwd < len(all_lines) and fwd <= i + 5:
                nxt = all_lines[fwd].content
                attr_block += " " + nxt
                if ")]" in nxt:
                    break
                fwd += 1

            has_payer = bool(RE_REALLOC_PAYER.search(attr_block))
            has_zero = bool(RE_REALLOC_ZERO.search(attr_block))

            if not has_payer or not has_zero:
                findings.append(
                    DetectionFinding(
                        rule_id="anchor.realloc_close",
                        concept_id="anchor.realloc_close",
                        category="rust_anchor",
                        severity=RiskSeverity.HIGH,
                        title="Unsafe Account Realloc Configuration",
                        message=(
                            "Account realloc constraint is missing realloc::payer or "
                            "realloc::zero specification."
                        ),
                        file_path=file_path,
                        line_number=line_num,
                        snippet=raw_line.strip(),
                        recommendation=(
                            "Specify 'realloc::payer = payer' and 'realloc::zero = false'."
                        ),
                        hunk_index=hunk_idx,
                    )
                )

        # Manual lamport zeroing close vulnerability
        if RE_MANUAL_LAMPORTS_ZERO.search(raw_line):
            nearby_lines = all_lines[max(0, i - 2) : min(len(all_lines), i + 4)]
            nearby_text = " ".join(item.content for item in nearby_lines)
            has_data_zero = (
                "zero" in nearby_text or "close = " in nearby_text or "realloc" in nearby_text
            )
            if not has_data_zero:
                findings.append(
                    DetectionFinding(
                        rule_id="anchor.realloc_close",
                        concept_id="anchor.realloc_close",
                        category="rust_anchor",
                        severity=RiskSeverity.HIGH,
                        title="Manual Lamport Zeroing Without Account Zeroing / Close Target",
                        message=(
                            "Setting account lamports directly to 0 without clearing data or "
                            "closing via Anchor enables revival attacks."
                        ),
                        file_path=file_path,
                        line_number=line_num,
                        snippet=raw_line.strip(),
                        recommendation=(
                            "Use Anchor's #[account(mut, close = recipient)] constraint."
                        ),
                        hunk_index=hunk_idx,
                    )
                )

        # 7. remaining_accounts iteration without length / owner / signer checks
        if "remaining_accounts" in raw_line and ("for " in raw_line or ".iter()" in raw_line):
            loop_lines = [item.content for item in all_lines[i : min(len(all_lines), i + 10)]]
            loop_text = " ".join(loop_lines)

            has_signer_check = "is_signer" in loop_text or "require!(acc.is_signer" in loop_text
            has_owner_check = "owner" in loop_text or "require_keys_eq!" in loop_text

            if not (has_signer_check or has_owner_check):
                findings.append(
                    DetectionFinding(
                        rule_id="anchor.remaining_accounts",
                        concept_id="anchor.remaining_accounts",
                        category="rust_anchor",
                        severity=RiskSeverity.HIGH,
                        title="Unchecked remaining_accounts Iteration",
                        message=(
                            "Iterating over ctx.remaining_accounts without verifying signer "
                            "status or account owner allows malicious accounts."
                        ),
                        file_path=file_path,
                        line_number=line_num,
                        snippet=raw_line.strip(),
                        recommendation=(
                            "Assert acc.is_signer and require_keys_eq!(*acc.owner, expected)."
                        ),
                        hunk_index=hunk_idx,
                    )
                )

        # 8. Unverified CPI target program id
        if RE_PROGRAM_ACCOUNT_INFO.search(raw_line):
            findings.append(
                DetectionFinding(
                    rule_id="anchor.unverified_cpi",
                    concept_id="anchor.cpi_checks",
                    category="rust_anchor",
                    severity=RiskSeverity.CRITICAL,
                    title="Unverified CPI Program Account (Using AccountInfo Instead of Program)",
                    message=(
                        "Program account is declared as AccountInfo<'info> rather than typed "
                        "Program<'info, T>. An attacker could pass a malicious program ID."
                    ),
                    file_path=file_path,
                    line_number=line_num,
                    snippet=raw_line.strip(),
                    recommendation="Use typed Program<'info, Token> or Program<'info, System>.",
                    hunk_index=hunk_idx,
                )
            )

    return findings
