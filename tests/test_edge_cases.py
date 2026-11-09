"""Edge case tests for detector robustness and false positive/negative prevention."""

from __future__ import annotations

from emc.detect import detect_risks
from emc.detect.ranking import compute_file_multiplier
from emc.detect.rust_anchor import _is_rust_file
from emc.ingest import IngestResult, parse_unified_diff


def _run_detect(diff_text: str, file_path: str = "programs/vault/src/lib.rs") -> list[str]:
    header = f"diff --git a/{file_path} b/{file_path}\n--- a/{file_path}\n+++ b/{file_path}\n"
    full_diff = header + diff_text
    files = parse_unified_diff(full_diff)
    ingest = IngestResult(files=files, raw_diff=full_diff, source="test")
    findings = detect_risks(ingest)
    return [f.rule_id for f in findings]


def test_windows_paths_multiplier() -> None:
    assert compute_file_multiplier(r"tests\test_vault.rs") == 0.3
    assert compute_file_multiplier(r"fixtures\detectors\test.diff") == 0.3
    assert compute_file_multiplier(r"docs\readme.md") == 0.3
    assert compute_file_multiplier(r"programs\vault\src\lib.rs") == 1.8


def test_is_rust_file_not_toml() -> None:
    assert not _is_rust_file("programs/vault/Cargo.toml")
    assert not _is_rust_file("programs/vault/README.md")
    assert _is_rust_file("programs/vault/src/lib.rs")


def test_multiline_anchor_signer_no_false_positive() -> None:
    diff = """@@ -10,4 +10,8 @@
 pub struct Withdraw<'info> {
+    #[account(
+        mut,
+        signer
+    )]
+    pub authority: AccountInfo<'info>,
 }"""
    rules = _run_detect(diff)
    assert "anchor.missing_signer" not in rules


def test_missing_signer_on_system_account() -> None:
    diff = """@@ -10,4 +10,5 @@
 pub struct Withdraw<'info> {
+    pub authority: SystemAccount<'info>,
 }"""
    rules = _run_detect(diff)
    assert "anchor.missing_signer" in rules


def test_invoke_signed_canonical_bumps_no_false_positive() -> None:
    diff = """@@ -10,4 +10,5 @@
 fn foo() {
+    invoke_signed(&ix, &accounts, &[&[b"vault", auth.key().as_ref(), &[ctx.bumps.vault]]])?;
 }"""
    rules = _run_detect(diff)
    assert "anchor.invoke_signed" not in rules


def test_multiline_seeds_missing_bump_detected() -> None:
    diff = """@@ -10,4 +10,9 @@
 pub struct Init<'info> {
+    #[account(
+        init,
+        payer = user,
+        seeds = [b"vault", user.key().as_ref()]
+    )]
+    pub vault: Account<'info, Vault>,
 }"""
    rules = _run_detect(diff)
    assert "anchor.pda_seeds" in rules


def test_multiline_seeds_with_bump_no_false_positive() -> None:
    diff = """@@ -10,4 +10,10 @@
 pub struct Init<'info> {
+    #[account(
+        init,
+        payer = user,
+        seeds = [b"vault", user.key().as_ref()],
+        bump
+    )]
+    pub vault: Account<'info, Vault>,
 }"""
    rules = _run_detect(diff)
    assert "anchor.pda_seeds" not in rules


def test_math_unchecked_arith_in_msg_no_false_positive() -> None:
    diff = """@@ -10,4 +10,5 @@
 fn foo() {
+    msg!("Current balance: {} - fee", balance);
 }"""
    rules = _run_detect(diff)
    assert "math.unchecked_arith" not in rules


def test_math_unchecked_arith_no_spaces_detected() -> None:
    diff = """@@ -10,4 +10,5 @@
 fn foo() {
+    vault.balance = balance-fee;
 }"""
    rules = _run_detect(diff)
    assert "math.unchecked_arith" in rules


def test_ts_hardcoded_rpc_in_comment_no_false_positive() -> None:
    diff = """@@ -10,4 +10,5 @@
+const rpc = process.env.SOLANA_RPC; // https://api.mainnet-beta.solana.com
"""
    rules = _run_detect(diff, file_path="src/wallet.ts")
    assert "ts.hardcoded_rpc" not in rules


def test_ts_lamport_units_reversed_operands_detected() -> None:
    diff1 = """@@ -10,4 +10,5 @@
+const fee = 0.05 * balance;
"""
    rules1 = _run_detect(diff1, file_path="src/wallet.ts")
    assert "ts.lamport_units" in rules1

    diff2 = """@@ -10,4 +10,5 @@
+const total = solAmount + balance;
"""
    rules2 = _run_detect(diff2, file_path="src/wallet.ts")
    assert "ts.lamport_units" in rules2


def test_ts_base_units_multiline_detected() -> None:
    diff = """@@ -10,4 +10,9 @@
+const ix = createTransferInstruction(
+    source,
+    destination,
+    owner,
+    10.5
+);
"""
    rules = _run_detect(diff, file_path="src/wallet.ts")
    assert "ts.base_units" in rules


def test_ts_address_validation_inside_longer_try_catch() -> None:
    diff = """@@ -10,4 +10,13 @@
+try {
+    const a = 1;
+    const b = 2;
+    const c = 3;
+    const d = 4;
+    const recipient = new PublicKey(userInput);
+    await sendTx(recipient);
+} catch (err) {
+    console.error(err);
+}
"""
    rules = _run_detect(diff, file_path="src/wallet.ts")
    assert "ts.address_validation" not in rules


def test_generic_bypass_flag_standard_type_ignore() -> None:
    diff = """@@ -10,4 +10,5 @@
+x = None # type: ignore
"""
    rules = _run_detect(diff, file_path="src/auth.py")
    assert "generic.bypass_flag" in rules


def test_generic_sensitive_log_camel_case() -> None:
    diff = """@@ -10,4 +10,5 @@
+console.log("User private key:", privateKey);
"""
    rules = _run_detect(diff, file_path="src/auth.ts")
    assert "generic.sensitive_log" in rules


def test_generic_hardcoded_fallback_bracket_and_rust() -> None:
    diff1 = """@@ -10,4 +10,5 @@
+const secret = process.env["API_SECRET"] || "default_secret";
"""
    rules1 = _run_detect(diff1, file_path="src/auth.ts")
    assert "generic.hardcoded_fallback" in rules1

    diff2 = """@@ -10,4 +10,5 @@
+let secret = std::env::var("APP_SECRET").unwrap_or("hardcoded_secret".to_string());
"""
    rules2 = _run_detect(diff2, file_path="programs/vault/src/lib.rs")
    assert "generic.hardcoded_fallback" in rules2
