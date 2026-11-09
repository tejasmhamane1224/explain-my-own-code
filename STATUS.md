# Project Status: explain-my-own-code (`emc`)

## Current Stage
**Stage 4: Session + Grading** -- **COMPLETED & HARDENED**

---

## Stage Progress Checklist
- [x] **Stage 0: Plan + Scaffold**: Repo layout, `CLAUDE.md`, `PLAN.md` with competitor comparison, `DECISIONS.md`, `STATUS.md`, CI workflow, Typer/Rich CLI skeleton (`init`, `quiz`, `explain`, `report`, `review`, `eval`, `doctor`, `config`, `hook`), hardened `emc doctor` diagnostics with corrupted config detection & safe key masking, comprehensive unit tests (24 passed).
- [x] **Stage 1: Ingest + Redact + Injection Fixtures**: Git diff ingestion (staged `git diff --cached`, commit range `git diff <rev>`, stdin), structured hunk splitting with exact 1-indexed line mapping (`DiffLine`, `DiffHunk`, `FileDiff`), `.emcignore` and lockfile/asset path filtering, diff/file size caps, secret redaction engine (Solana keypair byte arrays, Solana Base58 private keys, EVM hex private keys, BIP-39 mnemonic phrases, API tokens including Google and HuggingFace, .env values, generic credentials) with 100% recall on secrets fixture set, untrusted diff encapsulation, prompt injection fixture suite (`fixtures/injections/`), `emc quiz --dry-run` displaying Rich summary, prompt injection warnings, and encapsulated redacted payload (57 tests passed).
- [x] **Stage 2: Detectors + Ranking (No LLM)**: Solana/Anchor rules (missing Signer, UncheckedAccount, unchecked math, PDA bump, invoke_signed, close/realloc, remaining_accounts, unverified CPI), TS wallet rules (lamports/decimals, base units, address validation, RPCs), generic rules, hunk ranking, taxonomy alignment (`concepts.yaml`), 32 positive & negative fixtures with 100% test pass rate, plus 16 adversarial edge-case scenarios covering multiline attributes, canonical bumps, macro log safety, and Windows path normalization (116 passed tests).
- [x] **Stage 3: LLM Layer + Generation + Validator**: Abstract provider interface (`LLMProvider`, `AnthropicProvider`, `FakeProvider`, `LocalProvider`), token usage & cost tracking, content-hashed disk cache under `.emc/cache/` with `--max-cost` and token budget enforcement, 5 canonical question schemas, question planner, 4-step quality gate (`snippet_grounding`, `no_answer_leak`, `independent_solvability`, `non_ambiguity`, `injection_instruction`), single-retry regeneration recovery, acceptance tests covering all rejection paths (177 passed tests).
- [x] **Stage 4: Session + Grading**: Interactive terminal quiz loop (Rich), progressive hint ladder with point penalties (-25% per hint), deterministic key/number/text/line matchers with disambiguation, LLM rubric judge for free-text explain-back questions with offline keyword fallback and prompt injection defenses, scriptable driver, non-interactive CI bypass, full CLI `emc quiz` integration with `--answers` and `--json` (219 passed tests).
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

## Stage 3 Deliverables Summary
1. **LLM Provider Layer (`src/emc/llm/`)**:
   - `LLMProvider` abstract base interface with `generate_text`, `generate_structured` (Pydantic validation), token usage accumulation, and cost tracking.
   - `AnthropicProvider`: Anthropic Messages API client supporting tool-use JSON schema structured output, model resolution from `EMC_MODEL` (default: `claude-3-7-sonnet-latest`), and published pricing tables.
   - `FakeProvider`: Configurable deterministic provider for unit testing and offline development supporting canned responses, scriptable queues, dynamic response handlers, simulated exceptions, and token counting.
   - `LocalProvider`: HTTP stub for local models (Ollama, llama.cpp, or local HTTP server) with JSON schema formatting constraint.
2. **Persistent Disk Cache (`src/emc/llm/cache.py`)**:
   - `DiskCache`: Content-hashed filesystem storage under `.emc/cache/` keyed by `sha256(diff_hash : model : sha256(prompt))`.
   - `CachedLLMProvider`: Transparent decorator wrapper returning cached responses with zero cost (`cost_usd = 0.0`) and preventing duplicate provider calls.
   - Native `--max-cost` and token budget checking and enforcement.
3. **Question Schemas & Planning (`src/emc/questions/schema.py` & `src/emc/plan/`)**:
   - 5 Canonical question types: `predict-output`, `what-breaks-if`, `consequence`, `spot-the-bug`, `explain-back`.
   - Pydantic models for `Question`, `Distractor`, `RubricCriterion`, `QualityGateRejection`, `ValidationResult`, `SolverSolution`, `AmbiguityEvaluation`, and `QuestionPlan`.
   - `RULE_STRATEGY_MAP` pairing Stage 2 static risk findings to targeted question types and templates with fallback strategy for open diff hunks.
4. **4-Step Quality Gate (`src/emc/questions/validate.py` & `src/emc/questions/generator.py`)**:
   - Step 1: Snippet Grounding (verbatim text existence and exact line range coverage in diff hunks).
   - Step 2: No Answer Leakage (prohibits correct option keys and substantive answers from leaking in stem or distractor explanations).
   - Step 3: Independent Solvability (automated solver pass solving question from diff alone and matching answer key).
   - Step 4: Non-Ambiguity (second pass flagging multiple defensible answers).
   - Step 5: Injection & External URL Defense (rejection of instruction override patterns and ungrounded external URLs).
   - `QuestionGenerator` orchestrating generation with single-retry recovery and rejection logging.
5. **Acceptance Test Suite (`tests/test_rejection_paths.py` & `tests/test_cli_stage3.py`)**:
   - 177 total unit and acceptance tests covering every rejection path: grounding mismatch, out-of-bounds line range, disconnected hunks, answer leak in stem/distractor (both key and explanation), solver mismatch/exception, ambiguity detection/exception, prompt injections in stems/mutants/explanations, delimiter collision, result tampering, schema violations, budget exceeded with immediate abort, and cache hit/miss lifecycle (including zero-cost cached replay on exhausted budgets).
6. **CLI Integration**:
   - `emc generate`: Generates validated questions via `--provider` (`fake`, `anthropic`, `local`) with `--json` support.
   - `emc quiz --dry-run`: Renders planned question table, and with `--generate` executes full generation and quality gate validation.

---

## Stage 4 Deliverables Summary
1. **Grading Models & Score Aggregation (`src/emc/grade/models.py`)**:
   - `GradeResult`: Individual question grade record tracking points awarded, base points, hints used, fractional penalty, and feedback.
   - `RubricCriterionEvaluation` & `RubricEvaluation`: Itemized multi-criteria scoring for free-text answers.
   - `ScoreBreakdown`: Session-level aggregation computing total points, percentage, hint counts, pass/fail threshold verdict, and results list.
2. **Deterministic Grading Engine (`src/emc/grade/deterministic.py`)**:
   - Exact case/punctuation-insensitive key matching (`A`, `a`, `Choice A`, `Option A`, `(A)`).
   - 1-based numeric option selection (`1` -> `A`, `2` -> `B`, `Option 1`, `Choice 1`).
   - Distractor collision defense: Exact matching against all distractors prior to partial matching, rejecting ambiguous multi-distractor substrings.
   - Spot-the-bug line number matching (`line 41`, `41`) with choice index disambiguation (bare numbers `1..N` treated as choice selections rather than falsely matching line numbers).
   - Progressive hint ladder penalties: -25% per revealed hint, capped at -75%.
3. **Rubric-Based LLM Judge & Deterministic Fallback (`src/emc/grade/rubric.py`)**:
   - Structured LLM evaluation for `explain-back` free-text responses via `RubricEvaluationLLMOutput` with strict score clamping.
   - Deterministic offline fallback using taxonomy concept matching (stripping category prefixes) and domain keyword set intersection (filtering rubric meta-words and requiring multi-token overlap).
   - Prompt injection defense scanning developer answers for override markers (`ignore previous instructions`, `passed: true`, delimiter collision) with instant rejection.
4. **Rich Terminal Quiz Interface (`src/emc/session/`)**:
   - `display.py`: Syntax-highlighted diff snippet panels (monokai), mutant bug boxes, question stems, styled choices, hint disclaimers, immediate feedback panels, and final summary tables with verdict banners.
   - `runner.py` (`SessionRunner`): Interactive question loop with hint ladder commands (`H`/`hint`), skip commands (`S`/`skip`), and quit commands (`Q`/`quit`).
   - Scriptable session driver: Accepts sequence, iterator, or multiline string of inputs for deterministic non-TTY testing.
   - CI & Non-TTY Bypass: Automatically detects `CI=true` or non-terminal environments and exits 0 cleanly unless a scripted input stream is provided.
5. **CLI Integration (`src/emc/cli.py`)**:
   - Wired `emc quiz` to execute interactive and scripted sessions on `--staged`, `--commit <rev>`, or `--stdin`.
   - Supports `--provider` (`fake`, `anthropic`, `local`), `--model`, `--max-cost`, `--answers` (with CSV quote and newline support), and `--json`.
   - Strict JSON contract fidelity on all early returns, skips, CI bypasses, and errors.
   - Configuration enforcement: Blocks `--skip` when `skip_allowed = false` in `.emc.toml`.
6. **Acceptance Test Suite (`tests/test_session.py` & `tests/test_grade.py`)**:
   - 219 total passing unit and acceptance tests covering: perfect scores, progressive hint ladder deductions, hint exhaustion, wrong answers, mixed scoring, rubric grading with LLM & fallback, prompt injection rejection, distractor substring collision rejection, spot-the-bug choice index disambiguation, skip commands, quit aborts, unexpected EOF, blank input filtering, CI non-interactive bypass, CI scripted execution, and machine-readable JSON output on all paths.

---

## Verification Commands
To verify Stage 4 independently, run from the `explain-my-own-code` directory:

```bash
# 1. Run complete unit and acceptance test suite (219 passing tests)
pytest

# 2. Check code formatting and linting
ruff check .
ruff format --check .

# 3. Check static types
mypy src tests

# 4. Run Stage 4 session and grading tests specifically
pytest tests/test_session.py tests/test_grade.py -v

# 5. Run scripted comprehension quiz end-to-end on positive Anchor fixture
Get-Content fixtures/detectors/anchor_missing_signer_positive.diff | emc quiz --stdin --provider fake --answers "A,A,A"

# 6. Run scripted quiz with hint ladder usage (-25% penalty)
Get-Content fixtures/detectors/anchor_missing_signer_positive.diff | emc quiz --stdin --provider fake --answers "H,A,A,A"

# 7. Run scripted quiz with machine-readable JSON output
Get-Content fixtures/detectors/anchor_missing_signer_positive.diff | emc quiz --stdin --provider fake --answers "A,A,A" --json
```
