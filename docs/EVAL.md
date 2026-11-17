# EMC Benchmark Evaluation & Ablation Report (`docs/EVAL.md`)

> **Report Generated:** 2026-11-17T10:13:16.699212+00:00 | **EMC Version:** `1.0.0`

## 1. Executive Summary & Headline Metrics

This document records the empirical evaluation of `explain-my-own-code` (`emc`) across
31 realistic seeded vulnerabilities (21 Anchor Rust, 10 TypeScript Solana wallet),
17 secret/credential fixtures, 5 adversarial prompt injection attack vectors, and
30 hand-labeled free-text developer explanations.

| Benchmark Metric | Measured Result | Target Threshold | Verdict |
| :--- | :---: | :---: | :---: |
| **Seeded-Bug Surfacing Rate** | **100.0%** (31/31) | >= 90.0% | PASS |
| **Grounded-Question Rate** | **100.0%** | 100.0% | PASS |
| **Secret Redaction Recall** | **100.0%** | 100.0% | PASS |
| **Injection-Resistance Rate** | **100.0%** | 100.0% | PASS |
| **Grader Agreement (Accuracy)** | **96.7%** (29/30) | >= 90.0% | PASS |
| **Grader Precision / Recall / F1** | **P: 93.3% / R: 100.0% / F1: 96.6%** | >= 90.0% | PASS |
| **Average Cost per Session** | **$0.0066 USD** | < $0.05 | PASS |
| **Total Pipeline Latency** | **48.1 ms** | < 500 ms | PASS |

---

## 2. Pipeline Latency Breakdown

Wall-clock time measured across each isolated stage of the comprehension pipeline:

| Pipeline Stage | Latency (ms) | Description |
| :--- | :---: | :--- |
| **1. Ingest & Split** | `13.46 ms` | Hunk splitting, 1-indexed line mapping, size caps |
| **2. Secret Redaction** | `7.15 ms` | Regex masking across Solana, EVM, API keys, BIP-39 |
| **3. Static Risk Detectors** | `13.72 ms` | Solana Anchor (8 rules) + TS Wallet (4 rules) + Generic (4 rules) |
| **4. Question Planning** | `0.30 ms` | Risk-weighted hunk ranking & question strategy mapping |
| **5. Quality Gate Validation** | `9.39 ms` | 4-step check: snippet grounding, no-leak, solvability, injection |
| **6. Rubric Grader Evaluation** | `4.14 ms` | Graded across 30 hand-labeled developer responses |
| **Total Pipeline Latency** | **`48.15 ms`** | Sub-second offline execution |

---

## 3. Grader Agreement Evaluation (30 Hand-Labeled Explanations)

To measure whether the automated rubric judge accurately mirrors senior security engineers,
30 developer explanations were hand-labeled with ground-truth pass/fail scores and criteria rationales.

- **Total Samples:** 30
- **True Positives (TP):** 14 (passed accurate explanations)
- **True Negatives (TN):** 15 (failed inadequate explanations)
- **False Positives (FP):** 1 (passed by keyword density)
- **False Negatives (FN):** 0 (none)
- **Accuracy:** **96.7%** (29/30)
- **Precision:** **93.3%**
- **Recall:** **100.0%**
- **F1-Score:** **96.6%**

---

## 4. Seeded Bug Benchmark Dataset (31 Realistic Diffs)

| Diff ID | Language | Concept | Rule ID | Difficulty | Result |
| :--- | :---: | :--- | :--- | :---: | :---: |
| `eval_anchor_01_missing_signer_vault` | rust | `anchor.signer_check` | `anchor.missing_signer` | medium | **SURFACED** |
| `eval_anchor_02_missing_signer_admin` | rust | `anchor.signer_check` | `anchor.missing_signer` | medium | **SURFACED** |
| `eval_anchor_03_missing_signer_freeze` | rust | `anchor.signer_check` | `anchor.missing_signer` | hard | **SURFACED** |
| `eval_anchor_04_unchecked_oracle` | rust | `anchor.account_types` | `anchor.unchecked_account` | medium | **SURFACED** |
| `eval_anchor_05_unchecked_treasury` | rust | `anchor.account_types` | `anchor.unchecked_account` | medium | **SURFACED** |
| `eval_anchor_06_unchecked_stub` | rust | `anchor.account_types` | `anchor.unchecked_account` | easy | **SURFACED** |
| `eval_anchor_07_math_deposit` | rust | `math.checked_arith` | `math.unchecked_arith` | easy | **SURFACED** |
| `eval_anchor_08_math_withdraw` | rust | `math.checked_arith` | `math.unchecked_arith` | easy | **SURFACED** |
| `eval_anchor_09_math_fee` | rust | `math.checked_arith` | `math.unchecked_arith` | medium | **SURFACED** |
| `eval_anchor_10_math_shares` | rust | `math.checked_arith` | `math.unchecked_arith` | medium | **SURFACED** |
| `eval_anchor_11_pda_missing_bump` | rust | `anchor.pda_seeds` | `anchor.pda_seeds` | medium | **SURFACED** |
| `eval_anchor_12_pda_hardcoded_bump` | rust | `anchor.pda_seeds` | `anchor.pda_seeds` | medium | **SURFACED** |
| `eval_anchor_13_pda_unconstrained` | rust | `anchor.pda_seeds` | `anchor.pda_seeds` | hard | **SURFACED** |
| `eval_anchor_14_invoke_signed_empty` | rust | `anchor.invoke_signed` | `anchor.invoke_signed` | medium | **SURFACED** |
| `eval_anchor_15_invoke_signed_no_bump` | rust | `anchor.invoke_signed` | `anchor.invoke_signed` | hard | **SURFACED** |
| `eval_anchor_16_realloc_no_payer` | rust | `anchor.realloc_close` | `anchor.realloc_close` | medium | **SURFACED** |
| `eval_anchor_17_realloc_no_zero` | rust | `anchor.realloc_close` | `anchor.realloc_close` | medium | **SURFACED** |
| `eval_anchor_18_close_manual` | rust | `anchor.realloc_close` | `anchor.realloc_close` | hard | **SURFACED** |
| `eval_anchor_19_remaining_signer` | rust | `anchor.remaining_accounts` | `anchor.remaining_accounts` | hard | **SURFACED** |
| `eval_anchor_20_unverified_cpi_token` | rust | `anchor.cpi_checks` | `anchor.unverified_cpi` | medium | **SURFACED** |
| `eval_anchor_21_unverified_cpi_system` | rust | `anchor.cpi_checks` | `anchor.unverified_cpi` | medium | **SURFACED** |
| `eval_ts_01_lamports_mix_sol` | typescript | `ts.lamport_units` | `ts.lamport_units` | easy | **SURFACED** |
| `eval_ts_02_lamports_float_div` | typescript | `ts.lamport_units` | `ts.lamport_units` | easy | **SURFACED** |
| `eval_ts_03_lamports_wrong_factor` | typescript | `ts.lamport_units` | `ts.lamport_units` | easy | **SURFACED** |
| `eval_ts_04_base_units_transfer` | typescript | `ts.base_units` | `ts.base_units` | medium | **SURFACED** |
| `eval_ts_05_base_units_mint_to` | typescript | `ts.base_units` | `ts.base_units` | medium | **SURFACED** |
| `eval_ts_06_base_units_hardcoded_scale` | typescript | `ts.base_units` | `ts.base_units` | easy | **SURFACED** |
| `eval_ts_07_address_validation_pubkey` | typescript | `ts.address_validation` | `ts.address_validation` | medium | **SURFACED** |
| `eval_ts_08_address_validation_len` | typescript | `ts.address_validation` | `ts.address_validation` | medium | **SURFACED** |
| `eval_ts_09_hardcoded_rpc_mainnet` | typescript | `ts.rpc_security` | `ts.hardcoded_rpc` | easy | **SURFACED** |
| `eval_ts_10_hardcoded_rpc_helius` | typescript | `ts.rpc_security` | `ts.hardcoded_rpc` | easy | **SURFACED** |

---

## 5. Ablation Study: EMC Pipeline vs Naive Single-Prompt Baseline

To prove the necessity of EMC's layered architecture (deterministic detectors, risk ranking, secret redactor, and 4-step quality gate), we ablated all components against a naive single-prompt baseline on the exact same dataset (`'Read this diff and make 3 quiz questions'`):

| Metric | Naive One-Prompt Baseline | EMC Full Pipeline | Delta | Architectural Cause |
| :--- | :---: | :---: | :---: | :--- |
| **Seeded-Bug Surfacing Rate** | 12.9% | **100.0%** | `+87.1%` | EMC deterministic static detectors target subtle vulnerabilities that naive prompts miss. |
| **Grounded-Question Rate** | 0.0% | **100.0%** | `+100.0%` | EMC 4-Step Quality Gate enforces strict verbatim line grounding and eliminates answer leakage. |
| **Redaction Recall** | 0.0% | **100.0%** | `+100.0%` | EMC strips Solana/EVM keys, BIP-39 phrases, and API credentials before untrusted transmission. |
| **Injection-Resistance Rate** | 0.0% | **100.0%** | `+100.0%` | EMC untrusted diff encapsulation and boundary enforcement neutralize prompt injection payloads. |
| **Quality Gate Pass Rate** | 0.0% | **100.0%** | `+100.0%` | Naive questions fail grounding and leak answers in stems; EMC questions pass all 4 gates. |
| **Secrets Leaked to LLM** | `17` | **`0`** | `-17` | Naive prompts send raw diffs; EMC redacts prior to network transmission |
| **Prompt Injections Exploited** | `5` | **`0`** | `-5` | Naive prompts follow untrusted instructions; EMC encapsulates payloads |

---

## 6. Known Failures & Edge Cases (Honest Reporting)

As required by the specification, all failures, edge cases, and known limitations are cataloged below:

- **`Grader Disagreement` on `ft_26_anchor_close_fail`:** Predicted passed = `True`, Ground truth = `False`. Rationale: Ignores the security revival attack risk completely.
