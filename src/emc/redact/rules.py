"""Regex and algorithmic rule definitions for detecting sensitive secrets."""

from __future__ import annotations

import re
from typing import Callable

from emc.redact.bip39_words import BIP39_WORDS
from emc.redact.models import RedactionFinding

BASE58_ALPHABET = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
VALID_BIP39_DELIMITERS = set(" \t\r\n+-,'\"[]()\\")

# Precompiled regular expressions
ANTHROPIC_KEY_RE = re.compile(r"\bsk-ant-[a-zA-Z0-9_\-]{20,}\b")
OPENAI_KEY_RE = re.compile(r"\bsk-(?:proj-|admin-)?[a-zA-Z0-9_\-]{20,}\b")
GOOGLE_API_KEY_RE = re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b")
HUGGINGFACE_KEY_RE = re.compile(r"\bhf_[a-zA-Z0-9]{34,}\b")
GITHUB_TOKEN_RE = re.compile(
    r"\b(?:(?:ghp|gho|ghu|ghs|ghr)_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{40,})\b"
)
AWS_KEY_ID_RE = re.compile(r"\b(?:AKIA|ASIA|AROA)[0-9A-Z]{16}\b")
AWS_SECRET_RE = re.compile(
    r"(?:aws_secret_access_key|aws_secret_key|secret_access_key)\s*[:=]\s*[\"']?([A-Za-z0-9/+=]{40})[\"']?",
    re.IGNORECASE,
)
STRIPE_KEY_RE = re.compile(r"\b(?:sk|rk)_(?:live|test)_[0-9a-zA-Z]{24,}\b")
SLACK_TOKEN_RE = re.compile(r"\bxox[baprs]-[0-9a-zA-Z]{10,48}\b")
BEARER_TOKEN_RE = re.compile(r"\bBearer\s+([a-zA-Z0-9_\-\.]{25,})\b")
SOLANA_RPC_QUERY_RE = re.compile(
    r"(https?://[^\s\"'`]+\?(?:[^\s\"'`]*&)?(?:api-key|key|token|auth)=)([a-zA-Z0-9_\-]+)"
)

# Hex private keys (0x followed by 64 hex chars, or raw 64 hex chars in sensitive assignments)
HEX_0X_KEY_RE = re.compile(r"\b0x[0-9a-fA-F]{64}\b")
HEX_ASSIGN_KEY_RE = re.compile(
    r"\b[A-Za-z0-9_]*(?:private_?key|secret_?key|priv_?key|signing_?key|signer_?key|wallet_?secret|payer_?key)[A-Za-z0-9_]*\s*[:=]\s*[\"']?([0-9a-fA-F]{64})[\"']?",
    re.IGNORECASE,
)

# Solana base58 private keys:
# Standalone 87-88 character Base58 string (64-byte keypair)
SOLANA_B58_STANDALONE_RE = re.compile(r"\b([1-9A-HJ-NP-Za-km-z]{87,88})\b")
# Base58 key in assignment or decode function (43 to 88 chars)
SOLANA_B58_ASSIGN_RE = re.compile(
    r"\b[A-Za-z0-9_]*(?:private_?key|secret_?key|payer_?key|signer_?key|keypair|wallet_?secret)[A-Za-z0-9_]*\s*[:=]\s*[\"']?([1-9A-HJ-NP-Za-km-z]{43,88})[\"']?"
    r"|\b(?:fromSecretKey|from_secret_key|decode)\s*\(\s*[\"']?([1-9A-HJ-NP-Za-km-z]{43,88})[\"']?",
    re.IGNORECASE,
)

# Keypair byte array: e.g. [12, 34, ..., 56] or Rust vec![] or Go []byte{}
KEYPAIR_ARRAY_RE = re.compile(
    r"(?:\[|vec!\[|Uint8Array\.from\(\[|\[\]byte\{)\s*([0-9a-fA-Fx\s,\+\-]{60,})\s*(?:\]|\)|\})",
    re.DOTALL,
)

# .env sensitive variable assignments (supporting optional diff markers + or -)
ENV_SECRET_LINE_RE = re.compile(
    r"^[ \t\+\-]*(?:export\s+)?"
    r"([A-Za-z0-9_]*(?:KEY|SECRET|TOKEN|PASS|PASSWORD|AUTH|CREDENTIAL|PRIVATE|DATABASE_URL|RPC_URL|ACCESS)[A-Za-z0-9_]*)"
    r"\s*=\s*(?:([\"'])(.*?)\2|([^\s#]+))",
    re.MULTILINE,
)

# Generic sensitive code assignments
GENERIC_SECRET_ASSIGN_RE = re.compile(
    r"\b[A-Za-z0-9_]*(?:client_?secret|api_?secret|access_?token|secret_?token|app_?secret|auth_?token)[A-Za-z0-9_]*\s*[:=]\s*[\"']([^\"'\s]{16,})[\"']",
    re.IGNORECASE,
)

PLACEHOLDER_VALUES = {
    "",
    "TODO",
    "CHANGEME",
    "YOUR_KEY_HERE",
    "xxx",
    "placeholder",
    "true",
    "false",
    "null",
    "localhost",
    "127.0.0.1",
}


def mask_secret(secret: str) -> str:
    """Produce a safe preview of a secret without leaking contents."""
    cleaned = secret.strip()
    if len(cleaned) <= 8:
        return "***"
    prefix = cleaned[:4]
    suffix = cleaned[-4:]
    return f"{prefix}...{suffix}"


def find_solana_keypair_arrays(text: str) -> list[RedactionFinding]:
    """Detect 32-to-64 integer or hex byte arrays representing Solana private keypairs."""
    findings: list[RedactionFinding] = []
    for match in KEYPAIR_ARRAY_RE.finditer(text):
        raw_inner = match.group(1)
        tokens = re.findall(r"\b(?:0x[0-9a-fA-F]{1,2}|\d{1,3})\b", raw_inner)
        if len(tokens) not in (32, 64):
            continue
        try:
            valid_bytes = all(0 <= int(t, 0) <= 255 for t in tokens)
        except ValueError:
            continue
        if valid_bytes:
            matched_str = match.group(0)
            findings.append(
                RedactionFinding(
                    rule_id="solana_keypair_array",
                    category="solana_keypair",
                    description=f"Solana {len(tokens)}-byte secret keypair array",
                    matched_text=matched_str,
                    masked_text=f"[{tokens[0]}, ..., {tokens[-1]}] ({len(tokens)} bytes)",
                    replacement="[REDACTED:solana_keypair_array]",
                    start_col=match.start(),
                    end_col=match.end(),
                )
            )
    return findings


def find_solana_base58_keys(text: str) -> list[RedactionFinding]:
    """Detect Solana Base58 private keys in standalone or assigned contexts."""
    findings: list[RedactionFinding] = []

    # 1. Standalone 87-88 char base58 strings
    for match in SOLANA_B58_STANDALONE_RE.finditer(text):
        candidate = match.group(1)
        if all(c in BASE58_ALPHABET for c in candidate):
            findings.append(
                RedactionFinding(
                    rule_id="solana_base58_key",
                    category="solana_keypair",
                    description="Solana 64-byte Base58 encoded secret key",
                    matched_text=candidate,
                    masked_text=mask_secret(candidate),
                    replacement="[REDACTED:solana_base58_key]",
                    start_col=match.start(1),
                    end_col=match.end(1),
                )
            )

    # 2. Assigned / decoded Base58 keys (43-88 chars)
    for match in SOLANA_B58_ASSIGN_RE.finditer(text):
        candidate = match.group(1) or match.group(2)
        start_col = match.start(1) if match.group(1) is not None else match.start(2)
        end_col = match.end(1) if match.group(1) is not None else match.end(2)
        if candidate and all(c in BASE58_ALPHABET for c in candidate):
            findings.append(
                RedactionFinding(
                    rule_id="solana_base58_key",
                    category="solana_keypair",
                    description="Solana Base58 secret key in variable or decode call",
                    matched_text=candidate,
                    masked_text=mask_secret(candidate),
                    replacement="[REDACTED:solana_base58_key]",
                    start_col=start_col,
                    end_col=end_col,
                )
            )

    return findings


def find_hex_private_keys(text: str) -> list[RedactionFinding]:
    """Detect 64-character (32-byte) hex private keys."""
    findings: list[RedactionFinding] = []

    # 0x prefixed 64 hex chars
    for match in HEX_0X_KEY_RE.finditer(text):
        matched = match.group(0)
        findings.append(
            RedactionFinding(
                rule_id="hex_private_key",
                category="hex_private_key",
                description="64-character 0x-prefixed hex private key",
                matched_text=matched,
                masked_text=mask_secret(matched),
                replacement="[REDACTED:hex_private_key]",
                start_col=match.start(),
                end_col=match.end(),
            )
        )

    # Assigned hex keys without 0x
    for match in HEX_ASSIGN_KEY_RE.finditer(text):
        candidate = match.group(1)
        findings.append(
            RedactionFinding(
                rule_id="hex_private_key",
                category="hex_private_key",
                description="64-character hex private key in sensitive assignment",
                matched_text=candidate,
                masked_text=mask_secret(candidate),
                replacement="[REDACTED:hex_private_key]",
                start_col=match.start(1),
                end_col=match.end(1),
            )
        )

    return findings


def find_bip39_seed_phrases(text: str) -> list[RedactionFinding]:
    """Detect 12, 15, 18, 21, or 24 word BIP-39 mnemonic seed phrases (case-insensitive)."""
    findings: list[RedactionFinding] = []
    word_pattern = re.compile(r"\b[A-Za-z]{3,8}\b")
    all_matches = list(word_pattern.finditer(text))

    if not all_matches:
        return findings

    # Exclude hyphenated words like "12-word" or "seed-phrase"
    matches: list[re.Match[str]] = []
    for m in all_matches:
        start, end = m.span()
        if start > 0 and text[start - 1] == "-":
            continue
        if end < len(text) and text[end] == "-":
            continue
        matches.append(m)

    valid_lengths = {12, 15, 18, 21, 24}
    idx = 0
    num_matches = len(matches)

    while idx < num_matches:
        if matches[idx].group(0).lower() not in BIP39_WORDS:
            idx += 1
            continue

        start_idx = idx
        while idx < num_matches and matches[idx].group(0).lower() in BIP39_WORDS:
            if idx > start_idx:
                gap = text[matches[idx - 1].end() : matches[idx].start()]
                if not all(c in VALID_BIP39_DELIMITERS for c in gap) or "\n\n" in gap:
                    break
                # Do not bridge across comment header line break
                if "\n" in gap:
                    prev_line_start = text.rfind("\n", 0, matches[idx - 1].start())
                    prev_line = text[prev_line_start + 1 : matches[idx - 1].start()]
                    if ("#" in prev_line or "//" in prev_line) and not any(
                        c in gap for c in (",", '"', "'", "[", "]", "`")
                    ):
                        break
            idx += 1

        length = idx - start_idx
        found = False

        if length in valid_lengths:
            matched_span = text[matches[start_idx].start() : matches[idx - 1].end()]
            first_w = matches[start_idx].group(0)
            last_w = matches[idx - 1].group(0)
            findings.append(
                RedactionFinding(
                    rule_id="bip39_seed_phrase",
                    category="bip39_seed",
                    description=f"BIP-39 mnemonic seed phrase ({length} words)",
                    matched_text=matched_span,
                    masked_text=f"{first_w} ... {last_w} ({length} words)",
                    replacement="[REDACTED:bip39_seed_phrase]",
                    start_col=matches[start_idx].start(),
                    end_col=matches[idx - 1].end(),
                )
            )
            found = True
        elif length > 12:
            # Check for candidate valid sub-windows (preferring longest: 24, 21, 18, 15, 12)
            for target_len in (24, 21, 18, 15, 12):
                if length >= target_len:
                    sub_start = idx - target_len
                    matched_span = text[matches[sub_start].start() : matches[idx - 1].end()]
                    first_w = matches[sub_start].group(0)
                    last_w = matches[idx - 1].group(0)
                    findings.append(
                        RedactionFinding(
                            rule_id="bip39_seed_phrase",
                            category="bip39_seed",
                            description=f"BIP-39 mnemonic seed phrase ({target_len} words)",
                            matched_text=matched_span,
                            masked_text=f"{first_w} ... {last_w} ({target_len} words)",
                            replacement="[REDACTED:bip39_seed_phrase]",
                            start_col=matches[sub_start].start(),
                            end_col=matches[idx - 1].end(),
                        )
                    )
                    found = True
                    break

        if not found:
            idx = start_idx + 1

    return findings


def find_api_keys(text: str) -> list[RedactionFinding]:
    """Detect Anthropic, OpenAI, GitHub, AWS, Stripe, Slack, and RPC tokens."""
    findings: list[RedactionFinding] = []

    # Anthropic
    for match in ANTHROPIC_KEY_RE.finditer(text):
        m = match.group(0)
        findings.append(
            RedactionFinding(
                rule_id="anthropic_api_key",
                category="api_key",
                description="Anthropic API key",
                matched_text=m,
                masked_text=mask_secret(m),
                replacement="[REDACTED:anthropic_api_key]",
                start_col=match.start(),
                end_col=match.end(),
            )
        )

    # OpenAI
    for match in OPENAI_KEY_RE.finditer(text):
        m = match.group(0)
        findings.append(
            RedactionFinding(
                rule_id="openai_api_key",
                category="api_key",
                description="OpenAI API key",
                matched_text=m,
                masked_text=mask_secret(m),
                replacement="[REDACTED:openai_api_key]",
                start_col=match.start(),
                end_col=match.end(),
            )
        )

    # Google / Gemini
    for match in GOOGLE_API_KEY_RE.finditer(text):
        m = match.group(0)
        findings.append(
            RedactionFinding(
                rule_id="google_api_key",
                category="api_key",
                description="Google / Gemini API key",
                matched_text=m,
                masked_text=mask_secret(m),
                replacement="[REDACTED:google_api_key]",
                start_col=match.start(),
                end_col=match.end(),
            )
        )

    # HuggingFace
    for match in HUGGINGFACE_KEY_RE.finditer(text):
        m = match.group(0)
        findings.append(
            RedactionFinding(
                rule_id="huggingface_token",
                category="api_key",
                description="HuggingFace API token",
                matched_text=m,
                masked_text=mask_secret(m),
                replacement="[REDACTED:huggingface_token]",
                start_col=match.start(),
                end_col=match.end(),
            )
        )

    # GitHub
    for match in GITHUB_TOKEN_RE.finditer(text):
        m = match.group(0)
        findings.append(
            RedactionFinding(
                rule_id="github_token",
                category="api_key",
                description="GitHub token",
                matched_text=m,
                masked_text=mask_secret(m),
                replacement="[REDACTED:github_token]",
                start_col=match.start(),
                end_col=match.end(),
            )
        )

    # AWS Key ID
    for match in AWS_KEY_ID_RE.finditer(text):
        m = match.group(0)
        findings.append(
            RedactionFinding(
                rule_id="aws_access_key_id",
                category="api_key",
                description="AWS Access Key ID",
                matched_text=m,
                masked_text=mask_secret(m),
                replacement="[REDACTED:aws_access_key_id]",
                start_col=match.start(),
                end_col=match.end(),
            )
        )

    # AWS Secret
    for match in AWS_SECRET_RE.finditer(text):
        sec = match.group(1)
        findings.append(
            RedactionFinding(
                rule_id="aws_secret_access_key",
                category="api_key",
                description="AWS Secret Access Key",
                matched_text=sec,
                masked_text=mask_secret(sec),
                replacement="[REDACTED:aws_secret_access_key]",
                start_col=match.start(1),
                end_col=match.end(1),
            )
        )

    # Stripe
    for match in STRIPE_KEY_RE.finditer(text):
        m = match.group(0)
        findings.append(
            RedactionFinding(
                rule_id="stripe_api_key",
                category="api_key",
                description="Stripe secret API key",
                matched_text=m,
                masked_text=mask_secret(m),
                replacement="[REDACTED:stripe_api_key]",
                start_col=match.start(),
                end_col=match.end(),
            )
        )

    # Slack
    for match in SLACK_TOKEN_RE.finditer(text):
        m = match.group(0)
        findings.append(
            RedactionFinding(
                rule_id="slack_token",
                category="api_key",
                description="Slack API token",
                matched_text=m,
                masked_text=mask_secret(m),
                replacement="[REDACTED:slack_token]",
                start_col=match.start(),
                end_col=match.end(),
            )
        )

    # Bearer tokens
    for match in BEARER_TOKEN_RE.finditer(text):
        tok = match.group(1)
        findings.append(
            RedactionFinding(
                rule_id="bearer_token",
                category="api_key",
                description="HTTP Bearer authentication token",
                matched_text=tok,
                masked_text=mask_secret(tok),
                replacement="[REDACTED:bearer_token]",
                start_col=match.start(1),
                end_col=match.end(1),
            )
        )

    # Solana RPC query param key
    for match in SOLANA_RPC_QUERY_RE.finditer(text):
        key = match.group(2)
        findings.append(
            RedactionFinding(
                rule_id="rpc_api_key",
                category="api_key",
                description="Solana RPC endpoint API key",
                matched_text=key,
                masked_text=mask_secret(key),
                replacement="[REDACTED:rpc_api_key]",
                start_col=match.start(2),
                end_col=match.end(2),
            )
        )

    return findings


def find_env_secrets(text: str) -> list[RedactionFinding]:
    """Detect assigned secret values in .env or configuration files."""
    findings: list[RedactionFinding] = []
    for match in ENV_SECRET_LINE_RE.finditer(text):
        var_name = match.group(1)
        val = match.group(3) if match.group(3) is not None else match.group(4)
        if not val or val.strip() in PLACEHOLDER_VALUES:
            continue
        cleaned = val.strip()
        start_col = match.start(3) if match.group(3) is not None else match.start(4)
        end_col = match.end(3) if match.group(3) is not None else match.end(4)
        findings.append(
            RedactionFinding(
                rule_id="env_secret",
                category="env_secret",
                description=f".env assignment value for '{var_name}'",
                matched_text=cleaned,
                masked_text=mask_secret(cleaned),
                replacement="[REDACTED:env_secret]",
                start_col=start_col,
                end_col=end_col,
            )
        )
    return findings


def find_generic_secrets(text: str) -> list[RedactionFinding]:
    """Detect generic high-entropy secret assignments in code."""
    findings: list[RedactionFinding] = []
    for match in GENERIC_SECRET_ASSIGN_RE.finditer(text):
        val = match.group(1)
        if val in PLACEHOLDER_VALUES:
            continue
        findings.append(
            RedactionFinding(
                rule_id="generic_secret",
                category="generic_secret",
                description="Generic sensitive credential assignment",
                matched_text=val,
                masked_text=mask_secret(val),
                replacement="[REDACTED:generic_secret]",
                start_col=match.start(1),
                end_col=match.end(1),
            )
        )
    return findings


SCAN_RULE_FUNCTIONS: list[Callable[[str], list[RedactionFinding]]] = [
    find_solana_keypair_arrays,
    find_solana_base58_keys,
    find_hex_private_keys,
    find_bip39_seed_phrases,
    find_api_keys,
    find_env_secrets,
    find_generic_secrets,
]
