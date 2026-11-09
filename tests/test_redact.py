"""Tests for secret redaction engine and 100% recall verification on secrets fixture set."""

from __future__ import annotations

import json
from pathlib import Path

from emc.redact import Redactor, mask_secret, redact_diff


def test_100_percent_recall_on_secrets_fixture_set() -> None:
    """Verify 100% recall on the secrets fixture set: all known secrets must be redacted."""
    fixtures_dir = Path(__file__).resolve().parent.parent / "fixtures" / "secrets"
    manifest_path = fixtures_dir / "manifest.json"
    assert manifest_path.exists(), f"Missing fixture manifest at {manifest_path}"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    redactor = Redactor()
    total_expected = len(manifest)
    detected_count = 0
    missed_secrets: list[dict[str, str]] = []

    # 1. Verify detection in individual fixture files
    for entry in manifest:
        rel_file = entry["file"]
        secret_val = entry["secret_value"]

        file_path = fixtures_dir / rel_file
        assert file_path.exists(), f"Fixture file {file_path} missing"
        content = file_path.read_text(encoding="utf-8")

        res = redactor.redact_text(content, file_path=rel_file)

        # Check secret is redacted: secret_val must not appear in redacted output
        if secret_val in res.redacted_text:
            missed_secrets.append(entry)
        else:
            detected_count += 1

    recall = detected_count / total_expected
    assert recall == 1.0, (
        f"Secrets fixture recall must be 100% (got {recall * 100:.1f}%). Missed: {missed_secrets}"
    )

    # 2. Verify detection and redaction across the consolidated git diff fixture
    diff_file = fixtures_dir / "secrets_staged.diff"
    assert diff_file.exists(), f"Diff fixture {diff_file} missing"
    diff_content = diff_file.read_text(encoding="utf-8")

    diff_res = redactor.redact_text(diff_content)
    assert diff_res.has_secrets
    assert diff_res.redaction_count >= total_expected

    # Ensure none of the manifest secrets leaked in the diff
    for entry in manifest:
        assert entry["secret_value"] not in diff_res.redacted_text, (
            f"Secret {entry['id']} leaked into redacted diff output!"
        )


def test_redact_solana_keypair_array() -> None:
    """Verify 64-byte and 32-byte Solana keypair arrays are redacted."""
    # 64-byte array
    array_64 = "[" + ", ".join(str(i % 256) for i in range(64)) + "]"
    snippet = f"const keypair = Keypair.fromSecretKey(Uint8Array.from({array_64}));"

    res = redact_diff(snippet)
    assert res.has_secrets
    assert "[REDACTED:solana_keypair_array]" in res.redacted_text
    assert array_64 not in res.redacted_text

    # 32-byte array
    array_32 = "[" + ", ".join(str((i * 7) % 256) for i in range(32)) + "]"
    snippet_32 = f"let secret = vec!{array_32};"
    res_32 = redact_diff(snippet_32)
    assert res_32.has_secrets
    assert "[REDACTED:solana_keypair_array]" in res_32.redacted_text


def test_redact_solana_base58_key() -> None:
    """Verify Solana Base58 private keys are detected and redacted."""
    # Standalone 88-char base58 string
    raw_b58 = (
        "5Mii7kHjXkPjZkY2G3a4B5c6D7e8F9g9H1i2J3k4L5m6N7o8P9q9R1s2T3u4V5w6X7y8Z9a9B1c2D3e4F5g6H7i8"
    )
    res = redact_diff(f'export const PRIVKEY = "{raw_b58}";')
    assert res.has_secrets
    assert "[REDACTED:solana_base58_key]" in res.redacted_text
    assert raw_b58 not in res.redacted_text

    # Assigned 44-char base58 secret key
    assigned_b58 = "4uQeVj5tqViQh7yWWGStvkEG1Zmhx6uasJtWCJziofMTSgmt"
    res2 = redact_diff(f'const secret_key = "{assigned_b58}";')
    assert res2.has_secrets
    assert "[REDACTED:solana_base58_key]" in res2.redacted_text


def test_redact_hex_private_key() -> None:
    """Verify 0x and raw 64-char hex private keys are redacted."""
    hex_key = "0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d"
    res = redact_diff(f"let key = {hex_key};")
    assert res.has_secrets
    assert "[REDACTED:hex_private_key]" in res.redacted_text
    assert hex_key not in res.redacted_text

    raw_hex = "6c89f36288ced34006297063fe7e436d23157a6c62fbe75560bdec87eb232ad4"
    res2 = redact_diff(f'let private_key = "{raw_hex}";')
    assert res2.has_secrets
    assert "[REDACTED:hex_private_key]" in res2.redacted_text
    assert raw_hex not in res2.redacted_text


def test_redact_bip39_seed_phrases() -> None:
    """Verify BIP-39 12-word and 24-word seed phrases are redacted."""
    phrase_12 = (
        "abandon ability able about above absent absorb abstract absurd abuse access accident"
    )
    res = redact_diff(f'const mnemonic = "{phrase_12}";')
    assert res.has_secrets
    assert "[REDACTED:bip39_seed_phrase]" in res.redacted_text
    assert phrase_12 not in res.redacted_text

    phrase_24 = (
        "zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo "
        "zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo vote"
    )
    res2 = redact_diff(f'mnemonic = "{phrase_24}"')
    assert res2.has_secrets
    assert "[REDACTED:bip39_seed_phrase]" in res2.redacted_text
    assert phrase_24 not in res2.redacted_text


def test_redact_api_keys() -> None:
    """Verify Anthropic, OpenAI, GitHub, AWS, Stripe, and RPC tokens are redacted."""
    text = (
        'const a = "sk-ant-api03-abcdef1234567890abcdef1234567890abcdef12345678";\n'
        'const b = "sk-proj-abc123def456ghi789jkl012mno345pqr678stu901vwx234yz";\n'
        'const c = "ghp_abcdefghijklmnopqrstuvwxyz0123456789";\n'
        'const d = "AKIAIOSFODNN7EXAMPLE";\n'
        f'const e = "{"sk_" + "live_"}51Abcdefghijklmnopqrstuvwxy";\n'
        'const f = "https://solana.rpc.com/?api-key=secret-rpc-key-12345";\n'
    )
    res = redact_diff(text)
    assert res.redaction_count == 6
    assert "sk-ant-" not in res.redacted_text
    assert "sk-proj-" not in res.redacted_text
    assert "ghp_" not in res.redacted_text
    assert "AKIA" not in res.redacted_text
    assert "secret-rpc-key-12345" not in res.redacted_text


def test_redact_env_secrets() -> None:
    """Verify .env sensitive variable values are redacted without clobbering keys."""
    env_content = (
        "DATABASE_PASSWORD=MySecretDbPassword!\n"
        "JWT_SECRET=super_secret_jwt_signature\n"
        "APP_ENV=production\n"
    )
    res = redact_diff(env_content)
    assert res.has_secrets
    assert "MySecretDbPassword!" not in res.redacted_text
    assert "super_secret_jwt_signature" not in res.redacted_text
    assert "DATABASE_PASSWORD=[REDACTED:env_secret]" in res.redacted_text
    # Non-secret should remain untouched
    assert "APP_ENV=production" in res.redacted_text


def test_benign_code_no_false_positives() -> None:
    """Verify normal code, small numbers, and commit hashes are not redacted."""
    benign_code = """
    // Normal comments with regular english words: about able above
    const gitCommitSha = "40ff4fc8654c608fbd6ca096ffc57e84ab4b60e6";
    const smallArray = [1, 2, 3, 4, 5];
    const isReady = true;
    function calculateTotal(price: number): number {
        return price * 1.1;
    }
    """
    res = redact_diff(benign_code)
    assert not res.has_secrets
    assert res.redacted_text == benign_code


def test_mask_secret_utility() -> None:
    """Verify secret masking provides safe previews without leaking body."""
    assert mask_secret("short") == "***"
    assert mask_secret("sk-ant-1234567890abcdef") == "sk-a...cdef"
    assert "1234567890ab" not in mask_secret("sk-ant-1234567890abcdef")
