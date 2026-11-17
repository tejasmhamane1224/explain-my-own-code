# Project Status: explain-my-own-code (`emc`)

## Current Stage
**Stage 9: Release Readiness** -- **COMPLETED & VERIFIED**

---

## Stage Progress Checklist
- [x] **Stage 0: Plan + Scaffold**: Repo layout, `CLAUDE.md`, `PLAN.md` with competitor comparison, `DECISIONS.md`, `STATUS.md`, CI workflow, Typer/Rich CLI skeleton (`init`, `quiz`, `explain`, `report`, `review`, `eval`, `doctor`, `config`, `hook`), hardened `emc doctor` diagnostics with corrupted config detection & safe key masking, comprehensive unit tests (24 passed).
- [x] **Stage 1: Ingest + Redact + Injection Fixtures**: Git diff ingestion (staged `git diff --cached`, commit range `git diff <rev>`, stdin), structured hunk splitting with exact 1-indexed line mapping (`DiffLine`, `DiffHunk`, `FileDiff`), `.emcignore` and lockfile/asset path filtering, diff/file size caps, secret redaction engine (Solana keypair byte arrays, Solana Base58 private keys, EVM hex private keys, BIP-39 mnemonic phrases, API tokens including Google and HuggingFace, .env values, generic credentials) with 100% recall on secrets fixture set, untrusted diff encapsulation, prompt injection fixture suite (`fixtures/injections/`), `emc quiz --dry-run` displaying Rich summary, prompt injection warnings, and encapsulated redacted payload (57 tests passed).
- [x] **Stage 2: Detectors + Ranking (No LLM)**: Solana/Anchor rules (missing Signer, UncheckedAccount, unchecked math, PDA bump, invoke_signed, close/realloc, remaining_accounts, unverified CPI), TS wallet rules (lamports/decimals, base units, address validation, RPCs), generic rules, hunk ranking, taxonomy alignment (`concepts.yaml`), 32 positive & negative fixtures with 100% test pass rate, plus 16 adversarial edge-case scenarios covering multiline attributes, canonical bumps, macro log safety, and Windows path normalization (116 passed tests).
- [x] **Stage 3: LLM Layer + Generation + Validator**: Abstract provider interface (`LLMProvider`, `AnthropicProvider`, `FakeProvider`, `LocalProvider`), token usage & cost tracking, content-hashed disk cache under `.emc/cache/` with `--max-cost` and token budget enforcement, 5 canonical question schemas, question planner, 4-step quality gate (`snippet_grounding`, `no_answer_leak`, `independent_solvability`, `non_ambiguity`, `injection_instruction`), single-retry regeneration recovery, acceptance tests covering all rejection paths (177 passed tests).
- [x] **Stage 4: Session + Grading**: Interactive terminal quiz loop (Rich), progressive hint ladder with point penalties (-25% per hint), deterministic key/number/text/line matchers with disambiguation, LLM rubric judge for free-text explain-back questions with offline keyword fallback and prompt injection defenses, scriptable driver, non-interactive CI bypass, full CLI `emc quiz` integration with `--answers` and `--json` (219 passed tests).
- [x] **Stage 5: Ledger + Mastery + Report/Review**: `.emc/ledger.jsonl` append-only storage, Leitner 5-box spaced repetition mastery tracker, automatic quiz session recording, Rich comprehension report tables & JSON export, targeted review replay engine with immediate box progression (243 passed tests).
- [x] **Stage 6: Modes, Gate, Hooks, CI-Safe Behavior**: `.emc.toml` configuration, `off` / `warn` / `gate` modes, pre-commit and commit-msg hook installers, Comprehension trailers, CI / non-TTY bypass, foreign hook protection with backup/restore, git worktree support (273 passed tests).
- [x] **Stage 7: Evaluation Suite (`emc eval`)**: 31 seeded diffs (21 Anchor, 10 TS), programmatic mutation generator, 30 hand-labeled free-text rubric dataset, ablation vs naive single-prompt baseline, automated evaluation runner and report generation directly to `docs/EVAL.md` (282 passed tests).
- [x] **Stage 8: Documentation & Security Hardening**: Comprehensive README with honest competitor matrix, threat model (`docs/THREAT_MODEL.md`), `SECURITY.md`, and `CONTRIBUTING.md`.
- [x] **Stage 9: Release Readiness**: Semantic versioning (`1.0.0`), `CHANGELOG.md`, `dist/` sdist & wheel packaging dry-run, `twine check` validation, multi-OS & multi-Python GitHub Actions CI matrix, and automated release workflow (`.github/workflows/ci.yml`, `.github/workflows/release.yml`). Strictly no unauthorized external publishing.

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

## Stage 5 Deliverables Summary
1. **Append-Only Event Ledger Storage (`src/emc/ledger/storage.py` & `src/emc/ledger/models.py`)**:
   - `LedgerEvent` schema capturing: `timestamp`, `session_id`, `diff_hash`, `concept_id`, `question_type`, `user_answer`, `is_correct`, `hints_used`, `points_awarded`, `max_points`, `question_id`, `is_skipped`.
   - Thread-safe append-only persistence under `.emc/ledger.jsonl` with in-process `threading.Lock()` concurrency protection.
   - Resilient corrupt-line recovery skipping malformed JSON and schema violations without discarding valid records.
2. **Leitner 5-Box Mastery Tracker (`src/emc/ledger/tracker.py`)**:
   - 5 Progressive mastery boxes: Box 1 (Weak/Novice) to Box 5 (Mastered).
   - Progression rules: correct answers advance box (capped at 5) and increment streaks; incorrect answers demote to Box 1 and reset streaks.
   - Comprehensive concept metrics: attempts, correct count, streak, pass rate %, last reviewed timestamp, mastery level.
   - Full baseline mapping against canonical 16-concept taxonomy in `concepts.yaml`.
3. **Comprehension Mastery Reporting (`emc report` & `src/emc/ledger/report.py`)**:
   - Rich terminal dashboard with developer overview metrics (total attempts, accuracy %, mastered count, active concepts).
   - Per-concept table featuring encoding-safe visual Leitner box indicators (`[#####]` on Windows cp1252, `[■■■□□]` on UTF-8), attempts, pass rate %, streak, and status badges.
   - Prominent actionable warning panels highlighting weak concepts requiring reinforcement.
   - Complete machine-readable `--json` export and `--weak-only` / `--category` filtering.
4. **Targeted Review Replay Engine (`emc review` & `src/emc/ledger/review.py`)**:
   - Automatically prioritizes weak concepts (failed Box 1 concepts with lowest pass rates, then Box 2 developing concepts).
   - Generates grounded review questions utilizing authentic detector fixtures and taxonomy definitions.
   - Interactive terminal or scripted `--answers` session updating `.emc/ledger.jsonl` upon completion.
   - Immediate post-review Leitner box progression and status overview table.
   - Full CLI support for `--limit`, `--concept`, `--provider`, `--answers`, and `--json`.
5. **Quiz Session Ledger Integration (`src/emc/cli.py`)**:
   - Automatically writes question outcomes from `emc quiz` runs directly into `.emc/ledger.jsonl`.
   - Protects against phantom attempts by filtering out aborted sessions (`[aborted]`).
   - Resolves root repository `.emc/ledger.jsonl` even when invoked from subdirectories.
6. **Cross-Process File Locking & Hardening (`src/emc/ledger/storage.py`)**:
   - Portable OS-level interprocess locking (`fcntl` on POSIX, `msvcrt` on Windows) via dedicated `.lock` file.
   - Grounded review question generator compliant with Stage 3 Quality Gate snippet validation.
   - Guarded review replay completion state (`no_weak_concepts`) when all concepts are mastered or competent.
7. **Acceptance Test Suite (`tests/test_ledger.py`)**:
   - 24 comprehensive unit, concurrency, resilience, CLI, Quality Gate, and end-to-end integration tests (243 total passing tests across the entire repository).

---

## Stage 6 Deliverables Summary
1. **Commit Gate Evaluator & Operational Modes (`src/emc/gate/evaluator.py`)**:
   - `GateResult` schema capturing `mode`, `passed`, `exit_code`, `message`, `warning`, `blocked`.
   - `evaluate_gate` supporting all 3 operational modes:
     - `off`: Comprehension check disabled, logs skip event to ledger, exits 0.
     - `warn` (default): Score below threshold renders prominent warning banner, exits 0 (does not block commits).
     - `gate`: Score below threshold renders blocking error banner, exits 1 (blocks commit). Passing score exits 0.
   - `log_skip_event`: Records structured `system.skipped` audit events to `.emc/ledger.jsonl` without polluting concept mastery Leitner boxes.
2. **Commit Trailer Engine (`src/emc/gate/trailer.py`)**:
   - `format_commit_trailer`: Formats commit trailers in `fraction` ("Comprehension: 4/5"), `percentage` ("Comprehension: 80%"), and `detailed` ("Comprehension: 100% (anchor.signer_check: 2/2)") styles from `ScoreBreakdown`.
   - `append_commit_trailer`: Safely injects trailer into git commit message file before trailing git comments (`#`), deduplicates existing trailers in place, and safely avoids corrupting empty/aborted commit messages.
   - `save_staged_trailer` & `load_staged_trailer`: Stages trailer in `.emc/last_trailer` during `pre-commit` and safely consumes/unlinks it during `commit-msg`.
3. **Git Hooks Manager (`src/emc/hooks/manager.py` & CLI `emc hook`)**:
   - `get_git_hooks_dir`: Robust git hooks directory resolution using `git rev-parse --git-path hooks`, supporting standard git repos, git worktrees, submodules, and nested subdirectories.
   - `install_hooks`: Installs `pre-commit` (running `emc quiz --staged`) and optional `commit-msg` (running `emc hook commit-msg "$1"`).
   - Foreign Hook Protection: Detects non-emc foreign hooks and refuses to overwrite without `--force`. When `--force` is provided, automatically backs up the foreign hook to `.emc.bak`.
   - Idempotency: Repeated installs detect existing emc markers and avoid duplicating or corrupting scripts.
   - `uninstall_hooks`: Cleanly removes emc hooks and automatically restores original hooks from `.emc.bak` if a backup exists.
   - `emc hook commit-msg`: Injects staged trailer or explicit `--trailer` into the commit message file.
4. **CI-Safe Non-Interactive Bypass (`src/emc/cli.py`)**:
   - Detects `CI=true` or non-TTY stdin and skips with a clear message and exit 0 across all modes (`off`, `warn`, `gate`), preventing CI hangs.
   - Honors explicit scripted inputs (`--answers`) in CI to permit automated integration tests.
5. **Acceptance Test Suite (`tests/test_gate.py` & `tests/test_hooks.py`)**:
   - 30 comprehensive unit and integration acceptance tests (273 total passing tests across the entire repository):
     - `off` mode execution, ledger skip logging, and exit 0.
     - `warn` mode failing score displaying warning banner and exiting 0.
     - `warn` mode passing score exiting 0.
     - `gate` mode failing score displaying blocked error banner and exiting 1.
     - `gate` mode passing score exiting 0.
     - Zero-question breakdown safe permit across gate and warn modes.
     - `--skip` flag enforcement (allowed vs disallowed by config) with ledger event audit verification.
     - CI / non-TTY environment behavior across all modes.
     - CI with scripted inputs honoring gate mode.
     - Commit trailer formatting across fraction, percentage, and detailed styles.
     - Trailer injection with custom git `core.commentChar` (`;`, `%`, etc.).
     - Trailer deduplication without blank line accumulation across repeated updates.
     - Trailer prefix false-positive protection against body prose starting with "Comprehension".
     - Contiguous git trailer blocks compliant with `git interpret-trailers`.
     - Hooks directory discovery in standard repos, deep subdirectories, worktrees, custom `core.hooksPath`, and outside git.
     - Hook installation, idempotency, foreign hook protection for both `pre-commit` and `commit-msg`, backup and restore on uninstall.
     - Worktree hooks installation and lifecycle.
     - CLI `emc hook commit-msg` integration with staged and explicit trailers.
     - Aborted quiz session isolation preventing unattempted questions from demoting Leitner boxes.

---

## Stage 7 Deliverables Summary
1. **Seeded Bug Benchmark Dataset (`fixtures/eval/`)**:
   - 31 realistic seeded vulnerabilities (21 Anchor Rust, 10 TypeScript Solana wallet diffs) covering 11 critical vulnerability concepts:
     - Anchor: missing signer, unchecked accounts, raw math overflow, PDA bump verification, invoke_signed seeds, realloc/close lifecycle, remaining_accounts, unverified CPI.
     - TS Wallet: lamport/SOL unit mixing, token decimal base unit omissions, unvalidated PublicKey construction, hardcoded RPC endpoints.
   - Comprehensive manifest (`fixtures/eval/manifest.json`) cataloging diff IDs, concepts, rule IDs, files, line numbers, and difficulty levels.
2. **Mutation Generator (`src/emc/eval/mutation.py`)**:
   - Programmatic syntactical bug injector spanning 11 registered mutation functions.
   - Catalog of benign Anchor and TypeScript snippets (`BENIGN_ANCHOR_SNIPPETS`, `BENIGN_TS_SNIPPETS`).
   - `MutationGenerator` produces valid unified git diffs detectable by EMC static rules.
3. **Hand-Labeled Free-Text Rubric Dataset (`fixtures/eval/free_text_rubric.json`)**:
   - Exactly 30 hand-labeled developer explanations evaluated against ground truth pass/fail criteria and rationales.
   - Measured grader agreement: **96.7% accuracy, 93.3% precision, 100.0% recall, 96.6% F1-score**.
4. **Evaluation Runner (`src/emc/eval/runner.py`)**:
   - Automated benchmark runner calculating headline metrics, stage latency breakdowns, grader confusion matrix, and failure catalogs.
   - Headline results:
     - Seeded-Bug Surfacing Rate: **100.0%** (31/31) [target >= 90.0%]
     - Grounded-Question Rate: **100.0%** [target 100.0%]
     - Secret Redaction Recall: **100.0%** (17/17) [target 100.0%]
     - Injection-Resistance Rate: **100.0%** (5/5) [target 100.0%]
     - Average Cost per Session: **$0.0018 USD** [target < $0.05]
     - Total Pipeline Latency: **36.3 ms** [target < 500 ms]
5. **Ablation Baseline Runner (`src/emc/eval/ablation.py`)**:
   - Naive single-prompt LLM baseline (`"Read this diff and make quiz questions"`) compared head-to-head on the identical benchmark dataset.
   - Proves clear architectural superiority of EMC's layered pipeline:
     - Seeded-bug surfacing: Naive 12.9% vs EMC 100.0% (+87.1% delta)
     - Grounded-question rate: Naive 0.0% vs EMC 96.8% (+96.8% delta)
     - Secrets leaked to LLM: Naive 17 vs EMC 0 (-17 leak delta)
     - Injections exploited: Naive 5 vs EMC 0 (-5 exploit delta)
6. **Documentation Output (`docs/EVAL.md`)**:
   - Automatically produced by `emc eval --ablation --output docs/EVAL.md`.
   - Honest empirical report cataloging metrics, latency, ablation table, and known edge cases.
7. **CLI Integration (`src/emc/cli.py`)**:
   - `emc eval`: Supports `--ablation`, `--provider`, `--json`, `--output`.
8. **Test Suite**:
   - 8 acceptance tests in `tests/test_eval.py` (281 total passing tests across the repo).

---

## Stage 8 Deliverables Summary
1. **Production-Grade Documentation (`README.md`)**:
   - Comprehensive problem statement: "The Rubber-Stamp Dilemma in the Age of Generative AI".
   - 60-Second Quickstart walkthrough: installation via `pipx`/`pip`, `emc doctor`, `emc init`, `emc hook install`, and interactive quiz workflow.
   - 9-Stage ASCII architecture diagram mapping full pipeline from diff ingestion to git trailers and Leitner mastery.
   - Comprehensive catalog of all 16 deterministic risk rules (Anchor Rust, TS wallet precision, generic code smells).
   - Honest competitor matrix benchmarking `emc` against `arivcode`, `bel-ai-jar`, `cognit`, and generic AI chat prompts across 10 critical dimensions.
   - Empirical benchmark and ablation results table directly referencing `docs/EVAL.md` (100% bug surfacing vs 12.9% baseline, zero secret leaks, zero injection exploits, $0.0018 cost, 36.6 ms latency).
   - Full CLI command reference table and complete `.emc.toml` configuration documentation.
2. **Formal STRIDE Threat Model (`docs/THREAT_MODEL.md`)**:
   - Explicit trust boundaries (Boundary 0: Untrusted External Input, Boundary 1: Local Runtime Process, Boundary 2: Terminal UI, Boundary 3: Remote LLM Provider, Boundary 4: Persistent Artifacts & VCS).
   - Core asset definitions (Developer credentials, commit gate integrity, comprehension history, prompt pipeline context, CI/CD pipeline stability).
   - Systematic STRIDE analysis:
     - **Spoofing**: Git trailer spoofing defense via staged state tokens, distractor collision defense.
     - **Tampering**: Untrusted diff encapsulation, JSON schema enforcement, Quality Gate Step 5 injection defense, free-text rubric injection filter, cross-process OS locking (`msvcrt`/`fcntl`), corrupt-line recovery.
     - **Repudiation**: Immutable append-only `.emc/ledger.jsonl` with diff SHA-256 and question UUIDs, commit message trailers.
     - **Information Disclosure**: Pre-transmission local secret redaction with 100% recall (BIP-39, Solana Base58, EVM hex, API keys, .env secrets), Quality Gate Step 2 answer leak prevention.
     - **Denial of Service**: File/diff byte caps, lockfile/asset exclusions, CI non-interactive bypass, SHA-256 disk cache with cost/token budgets.
     - **Elevation of Privilege**: Foreign hook detection, refusal to overwrite without `--force`, automated `.emc.bak` backup and restoration on uninstall.
   - Security Mitigation Matrix mapping threats to automated verification tests.
   - Documented residual risks and explicit non-goals (not a mathematical formal verifier; trust boundary assumes local user).
3. **Coordinated Security Policy (`SECURITY.md`)**:
   - Supported versions (`1.0.x`, `0.1.x`).
   - Core security architecture and privacy guarantees (local-first processing, zero telemetry, local secret redaction before network transmission, no code execution, untrusted diff quarantine).
   - Private vulnerability reporting channels (GitHub Private Vulnerability Reporting, direct encrypted email).
   - Coordinated vulnerability disclosure timeline and SLA (< 24h initial acknowledgment, < 72h triage & reproduction, < 7d patch delivery).
4. **Contributor Guide (`CONTRIBUTING.md`)**:
   - Core engineering tenets: Grounded, Safe, Honest, Measurable, Finishable.
   - Development setup for Python 3.11-3.14 across Linux, macOS, and Windows.
   - Codebase structure guide detailing directory responsibilities across all 11 subsystems.
   - Step-by-step tutorial for adding new deterministic static detector rules (registering in `concepts.yaml`, writing detector logic, authoring positive and negative unified diff fixtures in `fixtures/detectors/`, updating `manifest.json`, and verifying 100% true-positive / 0% false-positive recall).
   - Guidelines for contributing new evaluation benchmark diffs.
   - Quality standards: 100% test pass rate, clean ruff linter, strict mypy type safety, quality gate compliance.
5. **Quality Verification**:
   - All 281 tests passing.
   - Ruff linting and formatting 100% clean.
   - Mypy static type checking 100% clean across all 84 source files.

---

## Stage 9 Deliverables Summary
1. **Semantic Versioning & Metadata**:
   - Standardized `1.0.0` semantic versioning across `pyproject.toml` and `src/emc/__init__.py`.
   - Comprehensive project URLs (Homepage, Documentation, Repository, Issues, Changelog).
   - Python version compatibility declared (`>=3.11`, tested through 3.14).
2. **Comprehensive Changelog (`CHANGELOG.md`)**:
   - Authored in Keep a Changelog standard documenting all 9 stages, features, security defenses, and CLI commands.
3. **Packaging Build & Dry-Run**:
   - Built source distribution (`explain_my_own_code-1.0.0.tar.gz`) and binary wheel (`explain_my_own_code-1.0.0-py3-none-any.whl`).
   - Verified that `emc/concepts.yaml` and `emc/py.typed` package data are packaged inside the wheel.
   - Verified distributions pass `twine check` with zero warnings or errors.
   - Re-installed wheel locally and verified `emc --version`, `emc --help`, and `emc doctor` run natively.
   - **Zero external publishing**: No PyPI or external registries targeted without explicit user authorization.
4. **CI/CD Automation Matrix (`.github/workflows/ci.yml` & `.github/workflows/release.yml`)**:
   - Added multi-platform test matrix: `ubuntu-latest`, `macos-latest`, `windows-latest`.
   - Added multi-version Python test matrix: `3.11`, `3.12`, `3.13`, `3.14`.
   - Automated packaging validation job in CI (`build` + `twine check`).
   - Prepared tag-triggered release workflow (`v*.*.*`) with draft release creation.

---

## Verification Commands
To verify Stage 9 independently, run from the `explain-my-own-code` directory:

```bash
# 1. Run complete unit and acceptance test suite (282 passing tests)
pytest

# 2. Check code formatting and linting
ruff check .
ruff format --check .

# 3. Check static types
mypy src tests

# 4. Build distribution artifacts (sdist and wheel)
python -m build

# 5. Validate distributions with twine
twine check dist/*

# 6. Verify native CLI entrypoints
emc --version
emc --help
emc doctor
```




