"""Deterministic static detectors for Rust and Anchor smart contract code."""

from __future__ import annotations

import re

from emc.detect.models import DetectionFinding, RiskSeverity
from emc.ingest.models import DiffHunk, FileDiff

RE_SIGNER_ATTR = re.compile(r"\bsigner\b")
RE_HAS_ONE_ATTR = re.compile(r"\bhas_one\s*=")

RE_AUTHORITY_FIELD = re.compile(
    r"^\s*pub(?:\s*\([^)]*\))?\s+(authority|owner|admin|payer|signer|user|creator|treasury|\w+_(?:authority|admin|owner|signer))\s*:\s*(.+?),?$"
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
RE_BUMP_IN_SEEDS = re.compile(
    r"&\[\s*(?:\*)?(?:ctx\.)?(?:bumps?\b|\w*bump\w*|\w*nonce\w*)", re.IGNORECASE
)

RE_REALLOC_PAYER = re.compile(r"\brealloc::payer\s*=")
RE_REALLOC_ZERO = re.compile(r"\brealloc::zero\s*=")
RE_MANUAL_LAMPORTS_ZERO = re.compile(
    r"\*{1,2}(?:\w+\.)*(?:lamports|try_borrow_mut_lamports)(?:\.borrow_mut\(\)|\(\))?\s*=\s*0"
)

RE_PROGRAM_ACCOUNT_INFO = re.compile(
    r"^\s*pub(?:\s*\([^)]*\))?\s+(\w*(?:program|token_program|system_program|cpi_program))\s*:\s*(?:AccountInfo|UncheckedAccount)<'info>"
)

FINANCIAL_KEYWORDS = [
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

RE_RAW_MATH = re.compile(
    r"(?:[a-zA-Z0-9_\)\]]\s*(?:\+|\*|\/|-(?!>))\s*[a-zA-Z0-9_\(\[]|\b\w+\s*[\+\-\*\/]=)"
)


def _is_rust_file(path: str) -> bool:
    """Check if file has Rust source extension."""
    clean = path.replace("\\", "/").lower()
    return clean.endswith(".rs")


def detect_rust_anchor_risks(file_diff: FileDiff) -> list[DetectionFinding]:
    """Analyze a single file diff for Rust and Anchor vulnerabilities."""
    findings: list[DetectionFinding] = []
    if not _is_rust_file(file_diff.path):
        return findings

    for hunk_idx, hunk in enumerate(file_diff.hunks):
        findings.extend(_detect_hunk_anchor_risks(file_diff.path, hunk_idx, hunk))

    return findings


def _extract_enclosing_attribute_block(all_lines: list, line_idx: int) -> str:
    """Extract full #[account(...)] attribute text around or preceding a given line index."""
    start_idx = line_idx
    while start_idx >= 0 and start_idx >= line_idx - 10:
        if all_lines[start_idx].line_type == "-":
            start_idx -= 1
            continue
        content = all_lines[start_idx].content.strip()
        if content.startswith("#[account"):
            break
        start_idx -= 1

    if start_idx < 0 or not all_lines[start_idx].content.strip().startswith("#[account"):
        return ""

    # Parse forward tracking parenthesis balance
    block_parts = []
    end_idx = start_idx
    open_parens = 0
    found_open = False

    while end_idx < len(all_lines) and end_idx <= start_idx + 15:
        if all_lines[end_idx].line_type == "-":
            end_idx += 1
            continue
        content = all_lines[end_idx].content
        block_parts.append(content)
        for ch in content:
            if ch == "(":
                open_parens += 1
                found_open = True
            elif ch == ")":
                open_parens -= 1
        if found_open and open_parens <= 0:
            break
        end_idx += 1

    return " ".join(block_parts)


def _get_field_attribute_block(all_lines: list, field_idx: int) -> str:
    """Extract #[account(...)] attribute decorating the struct field at field_idx."""
    lookback = field_idx - 1
    # Skip any deleted lines immediately preceding the field
    while lookback >= 0 and all_lines[lookback].line_type == "-":
        lookback -= 1

    if lookback < 0:
        return ""

    last_line = all_lines[lookback].content.strip()
    if not (
        last_line.endswith(")]") or last_line.startswith("#[account") or last_line.endswith("]")
    ):
        return ""

    # Find the start of the attribute block
    start_idx = lookback
    while start_idx >= 0 and start_idx >= field_idx - 15:
        if all_lines[start_idx].line_type == "-":
            start_idx -= 1
            continue
        c = all_lines[start_idx].content.strip()
        if c.startswith("#[account"):
            break
        start_idx -= 1

    if start_idx < 0 or not all_lines[start_idx].content.strip().startswith("#[account"):
        return ""

    # Assemble attribute lines from start_idx through lookback
    lines = [
        all_lines[k].content
        for k in range(start_idx, lookback + 1)
        if all_lines[k].line_type != "-"
    ]
    return " ".join(lines)


def _detect_hunk_anchor_risks(
    file_path: str, hunk_idx: int, hunk: DiffHunk
) -> list[DetectionFinding]:
    """Scan a hunk for all Anchor and Rust vulnerability rules."""
    findings: list[DetectionFinding] = []
    all_lines = hunk.lines

    reported_seeds_lines: set[int] = set()
    reported_realloc_lines: set[int] = set()

    for i, line in enumerate(all_lines):
        if line.line_type != "+":
            continue

        raw_line = line.content
        line_num = line.new_line_number

        # 1. UncheckedAccount without proper safety comment
        if RE_UNCHECKED_ACCOUNT.search(raw_line):
            has_valid_check = False
            lookback_idx = i - 1

            # Skip deleted lines and attribute blocks preceding this field
            in_attr = False
            while lookback_idx >= 0 and lookback_idx >= i - 10:
                if all_lines[lookback_idx].line_type == "-":
                    lookback_idx -= 1
                    continue

                prev_line = all_lines[lookback_idx].content.strip()
                if prev_line.endswith(")]") and "#[account" not in prev_line:
                    in_attr = True
                    lookback_idx -= 1
                    continue
                if in_attr:
                    if prev_line.startswith("#[account"):
                        in_attr = False
                    lookback_idx -= 1
                    continue
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

            vulnerable_types = (
                "AccountInfo",
                "Account<",
                "UncheckedAccount",
                "SystemAccount",
                "Box<Account<",
            )
            is_vulnerable_type = any(field_type.startswith(vt) for vt in vulnerable_types)
            is_signer_type = (
                "Signer<" in field_type or field_type.startswith("&") and "Signer<" in field_type
            )

            if is_vulnerable_type and not is_signer_type:
                attr_text = _get_field_attribute_block(all_lines, i)
                has_signer_protection = bool(
                    RE_SIGNER_ATTR.search(attr_text) or RE_HAS_ONE_ATTR.search(attr_text)
                )

                if not has_signer_protection:
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
        line_no_comment = re.sub(r"//.*$", "", raw_line).strip()
        if (
            line_no_comment
            and not line_no_comment.startswith("/*")
            and not line_no_comment.startswith("*")
            and not line_no_comment.startswith("use ")
            and not line_no_comment.startswith("pub trait")
        ):
            # Exclude macro logs (e.g. msg!, println!) and assertion/require calls
            is_log_or_assert = bool(
                re.search(
                    r"\b(?:msg!|println!|eprintln!|panic!|assert!|require!|format!)\s*\(",
                    line_no_comment,
                )
            )
            if not is_log_or_assert:
                # Strip string literals to avoid operator matching inside strings
                code_only = re.sub(r'"(?:\\.|[^"\\])*"', '""', line_no_comment)
                has_checked = bool(RE_CHECKED_OR_SATURATING.search(code_only))
                if not has_checked:
                    has_fin_var = any(
                        re.search(rf"\b{k}\b", code_only, re.IGNORECASE) for k in FINANCIAL_KEYWORDS
                    )
                    has_raw_math = bool(RE_RAW_MATH.search(code_only))
                    is_loop = "for " in code_only or "while " in code_only
                    is_size_const = "const " in code_only and (
                        "SIZE" in code_only or "LEN" in code_only
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
        if "seeds" in raw_line:
            attr_block = _extract_enclosing_attribute_block(all_lines, i)
            if not attr_block and "#[account" in raw_line:
                attr_block = raw_line

            if "seeds" in attr_block and line_num not in reported_seeds_lines:
                reported_seeds_lines.add(line_num if line_num is not None else 0)
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
            while fwd < len(all_lines) and fwd <= i + 15:
                call_text += " " + all_lines[fwd].content
                if ");" in all_lines[fwd].content or ")?" in all_lines[fwd].content:
                    break
                fwd += 1

            has_empty_seeds = "&[]" in call_text or "&[&[]]" in call_text
            has_bump_in_seeds = bool(RE_BUMP_IN_SEEDS.search(call_text))

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
        if "realloc" in raw_line:
            attr_block = _extract_enclosing_attribute_block(all_lines, i)
            if not attr_block and "#[account" in raw_line:
                attr_block = raw_line

            if "realloc" in attr_block and line_num not in reported_realloc_lines:
                reported_realloc_lines.add(line_num if line_num is not None else 0)
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
            preceding_lines = [
                item.content for item in all_lines[max(0, i - 6) : i] if item.line_type != "-"
            ]
            preceding_text = " ".join(preceding_lines)
            has_len_check = (
                "len()" in preceding_text
                or "is_empty()" in preceding_text
                or "require!" in preceding_text
            )

            loop_lines = [item.content for item in all_lines[i : min(len(all_lines), i + 12)]]
            loop_text = " ".join(loop_lines)

            has_signer_check = "is_signer" in loop_text or "require!(acc.is_signer" in loop_text
            has_owner_check = (
                "owner" in loop_text
                or "require_keys_eq!" in loop_text
                or ".key()" in loop_text
                or "key ==" in loop_text
            )

            if not (has_len_check or has_signer_check or has_owner_check):
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
