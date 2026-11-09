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
    r"\b(?:lamports|balance|balanceLamports)\s*(\+|-)\s*"
    r"(?:\d+(?:\.\d+)?|\b(?:sol|solAmount)\b)(?!\s*\*\s*LAMPORTS_PER_SOL)"
)
RE_FLOAT_MATH_BALANCE = re.compile(
    r"\b(?:lamports|balance|totalBalance|tokenBalance)\s*(\*|/)\s*(?:0\.\d+|1e\d+|\d+\.\d+)"
)
RE_WRONG_SOL_FACTOR = re.compile(r"\b(?:sol|solAmount)\s*\*\s*(?:1000|100000|1000000)\b")

# Base units vs human units
RE_UNSCALED_TRANSFER = re.compile(
    r"\b(?:createTransferInstruction|transferChecked|createMintToInstruction|mintTo)\s*\("
    r"[^)]*?,\s*(\d+(?:\.\d+)?|\b(?:amount|uiAmount)\b)\s*(?:,|\))"
)
RE_HARDCODED_DECIMALS_SCALE = re.compile(r"\b(?:amount|uiAmount)\s*\*\s*(?:100|1000|10000)\b")


def _is_ts_file(path: str) -> bool:
    """Check if file is TypeScript or JavaScript."""
    clean = path.lower()
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

        # Skip comment lines
        if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            continue

        # 1. Hardcoded RPC URLs
        rpc_match = RE_HARDCODED_RPC.search(raw_line)
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
        has_mix = bool(RE_MIX_SOL_LAMPORTS.search(raw_line))
        has_float = bool(RE_FLOAT_MATH_BALANCE.search(raw_line))
        has_wrong_factor = bool(RE_WRONG_SOL_FACTOR.search(raw_line))

        # Ignore if BN or BigInt is properly wrapping the expression
        has_safe_bn = (
            "new BN" in raw_line or "BigInt(" in raw_line or "LAMPORTS_PER_SOL" in raw_line
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
        has_unscaled = bool(RE_UNSCALED_TRANSFER.search(raw_line))
        has_hardcoded_scale = bool(RE_HARDCODED_DECIMALS_SCALE.search(raw_line))

        has_proper_scale = (
            "decimals" in raw_line
            or "parseUnits" in raw_line
            or "10 **" in raw_line
            or "Math.pow" in raw_line
            or "uiAmountToAmount" in raw_line
            or "BigInt(" in raw_line
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
        if RE_NAIVE_ADDR_LEN.search(raw_line):
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
        pk_match = RE_NEW_PUBLICKEY.search(raw_line)
        if pk_match:
            arg = pk_match.group(1).strip()
            # If it's a known constant or string literal, don't flag
            is_const = arg.startswith('"') or arg.startswith("'") or arg == ""
            if not is_const:
                lookback = max(0, i - 4)
                surrounding_lines = all_lines[lookback : min(len(all_lines), i + 5)]
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
