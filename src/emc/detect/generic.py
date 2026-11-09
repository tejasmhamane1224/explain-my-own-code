"""Deterministic static detectors for generic diff code smells and security risks."""

from __future__ import annotations

import re

from emc.detect.models import DetectionFinding, RiskSeverity
from emc.ingest.models import DiffHunk, FileDiff

# Bypass flag patterns
RE_BYPASS_FLAGS = [
    (
        re.compile(r"\b(?:skip_auth|bypass_auth|disable_auth)\s*(?:=|:)\s*(?:true|True|1)\b"),
        "Auth bypass flag explicitly enabled",
    ),
    (
        re.compile(r"\b(?:no_verify|disable_verify)\s*(?:=|:)\s*(?:true|True|1)\b"),
        "Verification bypass flag enabled",
    ),
    (
        re.compile(r"\bverify\s*(?:=|:)\s*(?:false|False|0)\b"),
        "Verification check explicitly disabled",
    ),
    (
        re.compile(r"\ballow_all\s*(?:=|:)\s*(?:true|True|1)\b"),
        "Unrestricted access flag (allow_all) enabled",
    ),
    (re.compile(r"\bdangerouslySetInnerHTML\b"), "dangerouslySetInnerHTML bypass used (XSS risk)"),
    (
        re.compile(r"\b(?:insecure|disable_security)\s*(?:=|:)\s*(?:true|True|1)\b"),
        "Security checks explicitly disabled",
    ),
    (
        re.compile(r"//\s*@ts-(?:ignore|nocheck)\b"),
        "TypeScript type safety explicitly ignored (@ts-ignore / @ts-nocheck)",
    ),
    (re.compile(r"#\s*type:\s*ignore\[.*\]"), "Python type checker suppression"),
]

# Sensitive logging patterns
RE_SENSITIVE_LOG = re.compile(
    r"\b(?:console\.(?:log|debug|info|warn|error)|logger\.(?:debug|info|warn|error)|"
    r"logging\.(?:debug|info|warn|error)|print|println!|eprintln!)\s*\([^)]*?\b"
    r"(private_key|secret_key|secret|password|passwd|auth_token|api_key|mnemonic|"
    r"seed_phrase|access_token|refresh_token)\b[^)]*?\)",
    re.IGNORECASE,
)

# Hardcoded secret fallbacks
RE_HARDCODED_FALLBACK = re.compile(
    r"""(?:process\.env\.(?:[A-Z0-9_]*(?:SECRET|KEY|PASSWORD|TOKEN|AUTH)[A-Z0-9_]*)\s*"""
    r"""(?:\|\||\?\?)\s*["'][^"']+["']|os\.(?:environ\.get|getenv)\s*\(\s*["']"""
    r"""[A-Z0-9_]*(?:SECRET|KEY|PASSWORD|TOKEN|AUTH)[A-Z0-9_]*["']\s*,\s*["'][^"']+["']\s*\)|"""
    r"""os\.(?:environ\.get|getenv)\s*\([^)]+\)\s+or\s+["'][^"']+["'])"""
)

# Empty catch / except patterns
RE_EMPTY_EXCEPT = re.compile(r"^\s*except(?:\s+[\w\s,()]+)?:\s*pass\s*$")
RE_EMPTY_CATCH = re.compile(r"^\s*catch\s*(?:\([^)]*\))?\s*\{\s*\}\s*$")


def detect_generic_risks(file_diff: FileDiff) -> list[DetectionFinding]:
    """Analyze a single file diff for high-risk generic code smells and security antipatterns."""
    findings: list[DetectionFinding] = []

    for hunk_idx, hunk in enumerate(file_diff.hunks):
        findings.extend(_detect_hunk_generic_risks(file_diff.path, hunk_idx, hunk))

    return findings


def _detect_hunk_generic_risks(
    file_path: str, hunk_idx: int, hunk: DiffHunk
) -> list[DetectionFinding]:
    """Scan a hunk for all generic code smell rules."""
    findings: list[DetectionFinding] = []
    all_lines = hunk.lines

    for i, line in enumerate(all_lines):
        if line.line_type != "+":
            continue

        raw_line = line.content
        line_num = line.new_line_number
        stripped = raw_line.strip()

        # 1. Security & Auth Bypass Flags
        for pattern, desc in RE_BYPASS_FLAGS:
            if pattern.search(raw_line):
                findings.append(
                    DetectionFinding(
                        rule_id="generic.bypass_flag",
                        concept_id="generic.bypass_flags",
                        category="generic",
                        severity=RiskSeverity.HIGH,
                        title=f"Security Bypass Flag Detected: {desc}",
                        message=(
                            f"Added line contains a high-risk security bypass ({desc}). "
                            "Bypasses should never be merged into production branches."
                        ),
                        file_path=file_path,
                        line_number=line_num,
                        snippet=raw_line.strip(),
                        recommendation=(
                            "Remove bypass flag and implement proper "
                            "authorization or verification logic."
                        ),
                        hunk_index=hunk_idx,
                    )
                )
                break

        # 2. Sensitive Variable Logging
        log_match = RE_SENSITIVE_LOG.search(raw_line)
        if log_match:
            var_name = log_match.group(1)
            findings.append(
                DetectionFinding(
                    rule_id="generic.sensitive_log",
                    concept_id="generic.sensitive_exposure",
                    category="generic",
                    severity=RiskSeverity.MEDIUM,
                    title=f"Sensitive Credential Logged to Output ('{var_name}')",
                    message=(
                        f"Logging statement appears to output sensitive variable '{var_name}'. "
                        "Credentials and private keys must never be written to stdout or logs."
                    ),
                    file_path=file_path,
                    line_number=line_num,
                    snippet=raw_line.strip(),
                    recommendation=(
                        "Remove sensitive variable from log output or mask before logging."
                    ),
                    hunk_index=hunk_idx,
                )
            )

        # 3. Hardcoded Fallbacks for Secrets
        if RE_HARDCODED_FALLBACK.search(raw_line):
            findings.append(
                DetectionFinding(
                    rule_id="generic.hardcoded_fallback",
                    concept_id="generic.hardcoded_fallbacks",
                    category="generic",
                    severity=RiskSeverity.HIGH,
                    title="Insecure Hardcoded Default for Secret / Password",
                    message=(
                        "Detected fallback to hardcoded string when secret env var is missing. "
                        "Applications must fail fast rather than using insecure defaults."
                    ),
                    file_path=file_path,
                    line_number=line_num,
                    snippet=raw_line.strip(),
                    recommendation=(
                        "Remove fallback default and fail fast if environment variable is missing."
                    ),
                    hunk_index=hunk_idx,
                )
            )

        # 4. Empty Catch / Except Blocks (Swallowed Errors)
        is_empty_catch = bool(RE_EMPTY_CATCH.match(stripped))
        is_empty_except = bool(RE_EMPTY_EXCEPT.match(stripped))

        # Check multi-line empty catch: catch (...) {\n}
        if stripped.startswith("catch") and "{" in stripped and "}" not in stripped:
            if i + 1 < len(all_lines) and all_lines[i + 1].content.strip() == "}":
                is_empty_catch = True

        # Check multi-line empty except: except Exception:\n pass
        if stripped.startswith("except") and stripped.endswith(":"):
            if i + 1 < len(all_lines) and all_lines[i + 1].content.strip() == "pass":
                is_empty_except = True

        if is_empty_catch or is_empty_except:
            findings.append(
                DetectionFinding(
                    rule_id="generic.empty_catch",
                    concept_id="generic.silent_error_handling",
                    category="generic",
                    severity=RiskSeverity.MEDIUM,
                    title="Silent Exception Swallowing (Empty Catch / Except)",
                    message=(
                        "Empty catch or except block silently swallows errors without handling. "
                        "This conceals critical security exceptions and unexpected failures."
                    ),
                    file_path=file_path,
                    line_number=line_num,
                    snippet=raw_line.strip(),
                    recommendation="Handle the exception explicitly, log the error, or re-raise.",
                    hunk_index=hunk_idx,
                )
            )

    return findings
