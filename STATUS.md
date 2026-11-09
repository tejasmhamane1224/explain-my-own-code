# Project Status: explain-my-own-code (`emc`)

## Current Stage
**Stage 2: Detectors + Ranking (No LLM)** -- **COMPLETED & HARDENED**

---

## Stage Progress Checklist
- [x] **Stage 0: Plan + Scaffold**: Repo layout, `CLAUDE.md`, `PLAN.md` with competitor comparison, `DECISIONS.md`, `STATUS.md`, CI workflow, Typer/Rich CLI skeleton (`init`, `quiz`, `explain`, `report`, `review`, `eval`, `doctor`, `config`, `hook`), hardened `emc doctor` diagnostics with corrupted config detection & safe key masking, comprehensive unit tests (24 passed).
- [x] **Stage 1: Ingest + Redact + Injection Fixtures**: Git diff ingestion (staged `git diff --cached`, commit range `git diff <rev>`, stdin), structured hunk splitting with exact 1-indexed line mapping (`DiffLine`, `DiffHunk`, `FileDiff`), `.emcignore` and lockfile/asset path filtering, diff/file size caps, secret redaction engine (Solana keypair byte arrays, Solana Base58 private keys, EVM hex private keys, BIP-39 mnemonic phrases, API tokens including Google and HuggingFace, .env values, generic credentials) with 100% recall on secrets fixture set, untrusted diff encapsulation, prompt injection fixture suite (`fixtures/injections/`), `emc quiz --dry-run` displaying Rich summary, prompt injection warnings, and encapsulated redacted payload (57 tests passed).
- [x] **Stage 2: Detectors + Ranking (No LLM)**: Solana/Anchor rules (missing Signer, UncheckedAccount, unchecked math, PDA bump, invoke_signed, close/realloc, remaining_accounts, unverified CPI), TS wallet rules (lamports/decimals, base units, address validation, RPCs), generic rules, hunk ranking, taxonomy alignment (`concepts.yaml`), 32 positive & negative fixtures with 100% test pass rate, plus 16 adversarial edge-case scenarios covering multiline attributes, canonical bumps, macro log safety, and Windows path normalization (116 passed tests).
- [ ] **Stage 3: LLM Layer + Generation + Validator**: Provider abstraction (Anthropic, Fake, Local), disk cache, question schemas, 4-step quality validator.
- [ ] **Stage 4: Session + Grading**: Interactive terminal quiz loop (Rich), hint ladder, deterministic matchers, LLM rubric judge for free text.
- [ ] **Stage 5: Ledger + Mastery + Report/Review**: `.emc/ledger.jsonl`, Leitner box mastery tracking, `emc report`, `emc review`.
- [ ] **Stage 6: Modes, Gate, Hooks, CI-Safe Behavior**: `.emc.toml` configuration, `off` / `warn` / `gate` modes, pre-commit hook installer, Comprehension trailer, CI bypass.
- [ ] **Stage 7: Evaluation Suite (`emc eval`)**: 30+ seeded diffs (20 Anchor, 10 TS), ablation vs naive single-prompt baseline, `docs/EVAL.md`.
- [ ] **Stage 8: Documentation & Security Hardening**: Comprehensive README with honest competitor matrix, threat model, `SECURITY.md`, `CONTRIBUTING.md`.
- [ ] **Stage 9: Release Readiness**: Packaging dry-run (`pipx`), changelog, versioning, GitHub Actions CI matrix.

---

## Stage 2 Deliverables Summary
1. **Concepts Taxonomy Registry (`concepts.yaml` & `src/emc/detect/taxonomy.py`)**:
   - 16 canonical concepts covering Solana/Anchor, TS wallet precision, and generic code smells.
   - Pydantic models `ConceptDefinition`, `TaxonomyRegistry` with validation, lookup, and fallback resolution.
2. **Deterministic Risk Detectors (`src/emc/detect/`)**:
   - `models.py`: `RiskSeverity` (CRITICAL=10.0, HIGH=5.0, MEDIUM=2.5, LOW=1.0, INFO=0.5), `DetectionFinding`, `RankedHunk`, `DetectionReport`.
   - `rust_anchor.py`: 8 Anchor smart contract rules:
     1. `anchor.missing_signer`: Privileged authority accounts lacking `Signer<'info>` or `#[account(signer)]` / `has_one`.
     2. `anchor.unchecked_account`: `UncheckedAccount` lacking safety doc comments (`/// CHECK:`).
     3. `math.unchecked_arith`: Unchecked raw arithmetic (`+`, `-`, `*`, `/`) on balances/amounts instead of `checked_*` or `saturating_*`.
     4. `anchor.pda_seeds`: PDA seeds constraints missing bump validation or using hardcoded bump literals.
     5. `anchor.invoke_signed`: `invoke_signed` calls with invalid, empty, or un-bumped signer seed slices.
     6. `anchor.realloc_close`: Realloc attributes missing payer/zero initialization, or manual lamport zeroing without close targets.
     7. `anchor.remaining_accounts`: Iteration over `remaining_accounts` without signer or owner verification.
     8. `anchor.unverified_cpi`: CPI program accounts typed as untyped `AccountInfo<'info>` instead of `Program<'info, T>`.
   - `ts_wallet.py`: 4 TypeScript & Solana wallet rules:
     9. `ts.lamport_units`: Mixing SOL and lamports, or float math on token balances without `BN`/`BigInt`.
     10. `ts.base_units`: Unscaled human amounts passed into token instructions without mint decimal scaling.
     11. `ts.address_validation`: `new PublicKey()` on dynamic input without `try/catch` or curve validation, and naive `.length === 44` checks.
     12. `ts.hardcoded_rpc`: Hardcoded production or sensitive RPC endpoints (`api.mainnet-beta.solana.com`, `helius-rpc.com`, etc.).
   - `generic.py`: 4 generic code smell rules:
     13. `generic.bypass_flag`: Bypass flags (`skip_auth`, `no_verify`, `@ts-ignore`, `dangerouslySetInnerHTML`).
     14. `generic.sensitive_log`: Logging passwords, private keys, secrets, or API tokens to console/logger.
     15. `generic.hardcoded_fallback`: Insecure defaults like `process.env.SECRET || "default_secret"`.
     16. `generic.empty_catch`: Swallowing exceptions with empty catch or except blocks.
   - `engine.py`: Orchestrates detection across all files, validates taxonomy alignment, and deduplicates findings.
3. **Hunk Risk Ranking Engine (`src/emc/detect/ranking.py`)**:
   - Multi-factor risk formula: `(Severity Weights + (Additions * 0.1 + Deletions * 0.03)) * File Multiplier`.
   - File importance weights: Smart contracts (1.8x), TS wallet/auth (1.5x), standard code (1.0x), docs/tests (0.3x).
   - Assigns sequential 1-based ranks and resolves primary mastery concept per hunk.
4. **Fixture Suite (`fixtures/detectors/`)**:
   - Positive AND negative fixtures for all 16 rules (32 unified diff fixtures).
   - `manifest.json`: Complete metadata matrix specifying rule ID, concept, fixture type, expected count, and description.
   - **100% true-positive recall on positive fixtures and 0% false positives on negative fixtures**.
5. **CLI Integration**:
   - `emc detect`: Analyzes diffs from staged, commit range, or stdin, outputting summary, risk findings, and ranked hunks in Rich tables or machine-readable `--json`.
   - `emc quiz --dry-run`: Integrated detector pipeline and ranked hunks into dry-run summary display.
6. **Test Suite**:
   - 116 passing unit and matrix tests across `tests/test_detectors.py`, `tests/test_edge_cases.py`, `tests/test_ranking.py`, `tests/test_taxonomy.py`, `tests/test_cli_detect.py`, `tests/test_cli_dry_run.py`, `tests/test_ingest.py`, `tests/test_redact.py`, `tests/test_injection.py`, `tests/test_doctor.py`, and `tests/test_cli.py`.

---

## Verification Commands
To verify Stage 2 independently, run from the `explain-my-own-code` directory:

```bash
# 1. Run complete unit test suite (116 passing tests)
pytest

# 2. Check code formatting and linting
ruff check .
ruff format --check .

# 3. Check static types
mypy src tests

# 4. Run detector test matrix specifically
pytest tests/test_detectors.py -v

# 5. Try emc detect on a positive Anchor smart contract fixture
Get-Content fixtures/detectors/anchor_missing_signer_positive.diff | emc detect --stdin

# 6. Try emc detect with JSON output
Get-Content fixtures/detectors/anchor_missing_signer_positive.diff | emc detect --stdin --json

# 7. Try dry-run with static risk detection on stdin
Get-Content fixtures/detectors/ts_hardcoded_rpc_positive.diff | emc quiz --stdin --dry-run
```
