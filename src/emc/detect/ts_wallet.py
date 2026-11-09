"""Deterministic static detectors for TypeScript and Solana wallet code."""

from __future__ import annotations

import re

from emc.detect.models import DetectionFinding, RiskSeverity
from emc.ingest.models import DiffHunk, FileDiff

# Known hardcoded RPC patterns
RE_HARDCODED_RPC = re.compile(
    r"""https?://(?:[a-zA-Z0-9_-]+\.)*(?:mainnet-beta\.solana\.com|"""
    r"""helius-rpc\.com|alchemy\.com/v2|ankr\.com/solana|genesysgo\.net|quicknode\.pro)""",
    re.IGNORECASE,
)

# Address validation patterns
RE_NEW_PUBLICKEY = re.compile(r"\bnew\s+PublicKey\s*\(([^)]+)\)")
RE_NAIVE_ADDR_LEN = re.compile(
    r"\b(?:address|pubkey|recipient|wallet)\.length\s*(?:===|==|>=|<=)\s*(?:32|43|44)\b"
)

# Lamport and decimal math patterns
RE_MIX_SOL_LAMPORTS = re.compile(
    r"(?:\b(?:lamports|balance|balanceLamports)\s*[\+\-]\s*(?:\d+(?:\.\d+)?|\b(?:sol|solAmount)\b)(?!\s*\*\s*LAMPORTS_PER_SOL)|"
    r"\b(?:sol|solAmount)\s*[\+\-]\s*(?:\d+(?:\.\d+)?|\b(?:lamports|balance|balanceLamports)\b))"
)
RE_FLOAT_MATH_BALANCE = re.compile(
    r"(?:\b(?:lamports|balance|totalBalance|tokenBalance)\s*[\*\/]\s*(?:0\.\d+|1e\d+|\d+\.\d+)|"
    r"(?:0\.\d+|\d+\.\d+)\s*[\*\/]\s*\b(?:lamports|balance|totalBalance|tokenBalance)\b)"
)
RE_WRONG_SOL_FACTOR = re.compile(r"\b(?:sol|solAmount)\s*\*\s*(?:1000|100000|1000000)\b")

# Base units vs human units
RE_TRANSFER_CALL_START = re.compile(
    r"\b(?:createTransferInstruction|transferChecked|createMintToInstruction|mintTo)\s*\("
)
RE_UNSCALED_TRANSFER = re.compile(
    r"\b(?:createTransferInstruction|transferChecked|createMintToInstruction|mintTo)\s*\("
    r"[^)]*?,\s*(\d+(?:\.\d+)?|\b(?:amount|uiAmount)\b)\s*(?:,|\))"
)
RE_HARDCODED_DECIMALS_SCALE = re.compile(r"\b(?:amount|uiAmount)\s*\*\s*(?:100|1000|10000)\b")


def _is_ts_file(path: str) -> bool:
    """Check if file is TypeScript or JavaScript."""
    clean = path.replace("\\", "/").lower()
    return clean.endswith((".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"))


def detect_ts_wallet_risks(file_diff: FileDiff) -> list[DetectionFinding]:
    """Analyze a single file diff for TypeScript wallet and Solana JS risks."""
    findings: list[DetectionFinding] = []
    if not _is_ts_file(file_diff.path):
        return findings

    for hunk_idx, hunk in enumerate(file_diff.hunks):
        findings.extend(_detect_hunk_ts_risks(file_diff.path, hunk_idx, hunk))

    return findings


def _detect_hunk_ts_risks(file_path: str, hunk_idx: int, hunk: DiffHunk) -> list[DetectionFinding]:
    """Scan a hunk for all TS wallet vulnerability rules."""
    findings: list[DetectionFinding] = []
    all_lines = hunk.lines

    for i, line in enumerate(all_lines):
        if line.line_type != "+":
            continue

        raw_line = line.content
        line_num = line.new_line_number
        stripped = raw_line.strip()

        # Skip full comment lines
        if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            continue

        # Strip inline comment without stripping https:// or http:// in URLs
        code_only = re.sub(r"(?<!:)\/\/.*$", "", raw_line).strip()
        if not code_only:
            continue

        # 1. Hardcoded RPC URLs (evaluated on code portion only)
        rpc_match = RE_HARDCODED_RPC.search(code_only)
        if rpc_match:
            findings.append(
                DetectionFinding(
                    rule_id="ts.hardcoded_rpc",
                    concept_id="ts.rpc_security",
                    category="ts_wallet",
                    severity=RiskSeverity.HIGH,
                    title="Hardcoded Production RPC Endpoint",
                    message=(
                        f"Hardcoded sensitive or production RPC URL: '{rpc_match.group(0)}'. "
                        "This exposes rate-limits, API keys, or cluster configurations."
                    ),
                    file_path=file_path,
                    line_number=line_num,
                    snippet=raw_line.strip(),
                    recommendation=(
                        "Load RPC URL dynamically from process.env.SOLANA_RPC_URL or clusterApiUrl."
                    ),
                    hunk_index=hunk_idx,
                )
            )

        # 2. Lamport & Decimal Scaling Precision
        has_mix = bool(RE_MIX_SOL_LAMPORTS.search(code_only))
        has_float = bool(RE_FLOAT_MATH_BALANCE.search(code_only))
        has_wrong_factor = bool(RE_WRONG_SOL_FACTOR.search(code_only))

        has_safe_bn = (
            "new BN" in code_only
            or "BigInt(" in code_only
            or "LAMPORTS_PER_SOL" in code_only
            or "Decimal" in code_only
        )
        if (has_mix or has_float or has_wrong_factor) and not has_safe_bn:
            findings.append(
                DetectionFinding(
                    rule_id="ts.lamport_units",
                    concept_id="ts.lamport_units",
                    category="ts_wallet",
                    severity=RiskSeverity.HIGH,
                    title="Improper Lamport Math / Float Precision on Balances",
                    message=(
                        "Detected mixing of SOL and lamports or float math on token balances. "
                        "JavaScript floating-point math causes silent precision loss."
                    ),
                    file_path=file_path,
                    line_number=line_num,
                    snippet=raw_line.strip(),
                    recommendation=(
                        "Use BigInt or BN.js and multiply explicitly by LAMPORTS_PER_SOL."
                    ),
                    hunk_index=hunk_idx,
                )
            )

        # 3. Base Units vs Human Units in Instructions
        has_unscaled = False
        has_hardcoded_scale = bool(RE_HARDCODED_DECIMALS_SCALE.search(code_only))

        if RE_TRANSFER_CALL_START.search(code_only):
            # Gather multiline instruction call text
            call_text = code_only
            fwd = i + 1
            while fwd < len(all_lines) and fwd <= i + 10:
                nxt = re.sub(r"(?<!:)\/\/.*$", "", all_lines[fwd].content).strip()
                call_text += " " + nxt
                if ");" in nxt or ")" in nxt:
                    break
                fwd += 1

            if RE_UNSCALED_TRANSFER.search(call_text) or re.search(
                r",\s*(?:\d+(?:\.\d+)?|\b(?:amount|uiAmount)\b)\s*(?:,|\))", call_text
            ):
                has_unscaled = True
        elif RE_UNSCALED_TRANSFER.search(code_only):
            has_unscaled = True

        has_proper_scale = (
            "decimals" in code_only
            or "parseUnits" in code_only
            or "10 **" in code_only
            or "Math.pow" in code_only
            or "uiAmountToAmount" in code_only
            or "BigInt(" in code_only
        )

        if (has_unscaled or has_hardcoded_scale) and not has_proper_scale:
            findings.append(
                DetectionFinding(
                    rule_id="ts.base_units",
                    concept_id="ts.base_units",
                    category="ts_wallet",
                    severity=RiskSeverity.HIGH,
                    title="Unscaled Human Amount Passed to On-Chain Instruction",
                    message=(
                        "Token instruction called with unscaled or improperly scaled amount. "
                        "On-chain SPL token instructions require base units."
                    ),
                    file_path=file_path,
                    line_number=line_num,
                    snippet=raw_line.strip(),
                    recommendation=(
                        "Scale UI amount by mint decimals: "
                        "BigInt(Math.floor(uiAmount * (10 ** mintDecimals)))."
                    ),
                    hunk_index=hunk_idx,
                )
            )

        # 4. Address Validation
        # Check naive string length check
        if RE_NAIVE_ADDR_LEN.search(code_only):
            findings.append(
                DetectionFinding(
                    rule_id="ts.address_validation",
                    concept_id="ts.address_validation",
                    category="ts_wallet",
                    severity=RiskSeverity.MEDIUM,
                    title="Naive Address Validation via String Length",
                    message=(
                        "Address validation relies on naive string length check. "
                        "Solana public keys are 32-byte base58 strings varying from 32-44 chars."
                    ),
                    file_path=file_path,
                    line_number=line_num,
                    snippet=raw_line.strip(),
                    recommendation=(
                        "Validate using PublicKey constructor in try/catch and PublicKey.isOnCurve."
                    ),
                    hunk_index=hunk_idx,
                )
            )

        # Check new PublicKey(arg) without try/catch
        pk_match = RE_NEW_PUBLICKEY.search(code_only)
        if pk_match:
            arg = pk_match.group(1).strip()
            # Skip string literal constants (single, double, or un-interpolated template quotes)
            is_const = (
                arg.startswith('"')
                or arg.startswith("'")
                or (arg.startswith("`") and "${" not in arg)
                or arg == ""
            )
            if not is_const:
                lookback = max(0, i - 15)
                surrounding_lines = all_lines[lookback : min(len(all_lines), i + 15)]
                surrounding_text = " ".join(item.content for item in surrounding_lines)
                has_try_catch = (
                    "try {" in surrounding_text
                    or "try{" in surrounding_text
                    or "catch" in surrounding_text
                )
                has_curve_check = "isOnCurve" in surrounding_text

                if not (has_try_catch or has_curve_check):
                    findings.append(
                        DetectionFinding(
                            rule_id="ts.address_validation",
                            concept_id="ts.address_validation",
                            category="ts_wallet",
                            severity=RiskSeverity.MEDIUM,
                            title="Unchecked PublicKey Instantiation",
                            message=(
                                f"Instantiating new PublicKey({arg}) on dynamic input without "
                                "try/catch or curve validation."
                            ),
                            file_path=file_path,
                            line_number=line_num,
                            snippet=raw_line.strip(),
                            recommendation=(
                                "Wrap 'new PublicKey(...)' in try/catch and check isOnCurve()."
                            ),
                            hunk_index=hunk_idx,
                        )
                    )

    return findings
