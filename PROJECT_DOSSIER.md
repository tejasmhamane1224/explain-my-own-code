# EXPLAIN-MY-OWN-CODE (`emc`) - COMPLETE PROJECT DOSSIER

**Location**: `c:\Users\TEJAS\Downloads\resume\explain-my-own-code`  
**Author**: Tejas Mhamane  
**Status**: Stage 7 Completed & 100% Verified (281 tests passing)  
**Primary Language/Runtime**: Python 3.11+, Poetry, Pytest, Typer, Rich, Pydantic  

---

## 1. Project Mission & Identity
`explain-my-own-code` (`emc`) is a local developer safety CLI and comprehension gating tool designed to eliminate "rubber-stamping" of AI-generated code. It intercepts staged git diffs (particularly Solana/Anchor Rust and TypeScript wallet logic), extracts high-risk hunks using deterministic static detectors, redacts all secrets/private keys, and forces developers to prove comprehension via targeted interactive quiz questions before commits are permitted.

---

## 2. Complete Technical Differentiation

| Dimension | `explain-my-own-code` (`emc`) | `jupiter-redesign` | `circuit-pay` |
| :--- | :--- | :--- | :--- |
| **Domain** | Developer tooling, AI code diff comprehension, static analysis & eval benchmarking | Web3 DeFi UX/UI redesign case study & interactive prototype | Solana batch payroll settlement protocol & treasury routing |
| **Primary Stack** | Python 3.11+, Typer, Rich, Pydantic, Anthropic SDK, Pytest, Ruff, Mypy | Next.js 16, React 19, Tailwind CSS v4, TypeScript | TypeScript, Next.js, Solana Web3.js / Anchor, Vitest |
| **Verification Evidence**| **281 passing unit/eval tests**, 96.7% grader agreement, 100% secret redaction recall | Interactive case study UI with before/after trade views & live states | **207 passing automated tests**, sub-second routing, deterministic batch execution |
| **Deliverable** | Full CLI (`emc init`, `quiz`, `detect`, `eval`, `report`, `review`, `hook`) | Web demo showcasing "Three Moments That Make or Break Trust on Jupiter" | Non-custodial payroll router with live dashboard & test evidence |
| **Origin / Goal** | Autonomous AI safety research & developer verification engine | Superteam India Open Design Bounty submission | Production-grade DeFi batch payment protocol |

---

## 3. Architecture & Core Subsystems

```
                               ┌────────────────────────────────┐
                               │   Git Diff Ingestion (CLI)     │
                               │  (staged / commit-range / stdin)│
                               └──────────────┬─────────────────┘
                                              ▼
                               ┌────────────────────────────────┐
                               │ Secret Redactor & Ingest Gate  │
                               │  - BIP-39, Solana Base58, EVM  │
                               │  - Prompt Injection Defense    │
                               └──────────────┬─────────────────┘
                                              ▼
                               ┌────────────────────────────────┐
                               │ Deterministic Detectors & Rank │
                               │  - 8 Anchor Rust Rules         │
                               │  - 4 TS Wallet Precision Rules │
                               │  - 4 Generic Code Smell Rules  │
                               └──────────────┬─────────────────┘
                                              ▼
                               ┌────────────────────────────────┐
                               │ LLM Layer & 4-Step Gate        │
                               │  - Snippet Grounding Check     │
                               │  - No Answer Leakage Check     │
                               │  - Independent Solvability     │
                               │  - Non-Ambiguity Check         │
                               │  - SHA-256 Content-Hashed Cache│
                               └──────────────┬─────────────────┘
                                              ▼
                               ┌────────────────────────────────┐
                               │ Interactive Session & Grading  │
                               │  - Rich Terminal Quiz Loop     │
                               │  - Progressive Hint Penalty    │
                               │  - Rubric Free-Text Judge      │
                               └──────────────┬─────────────────┘
                                              ▼
        ┌─────────────────────────────────────┴─────────────────────────────────────┐
        ▼                                                                           ▼
┌──────────────────────────────┐                            ┌──────────────────────────────┐
│ Leitner 5-Box Mastery Ledger │                            │ Commit Gating & Git Hooks    │
│  - `.emc/ledger.jsonl`       │                            │  - `pre-commit` & `commit-msg`│
│  - Concept Weakness Tracking │                            │  - Mode: off / warn / gate   │
│  - Targeted Replay Review    │                            │  - Comprehension Git Trailer │
└──────────────────────────────┘                            └──────────────────────────────┘
```

---

## 4. Complete File Inventory

- **Root Configurations**:
  - `pyproject.toml`: Poetry build definition, dependencies, CLI entrypoint `emc = "emc.cli:app"`.
  - `.emc.toml`: Operational settings (`mode = "warn"`, `threshold = 70`, `skip_allowed = true`).
  - `CLAUDE.md` / `PLAN.md` / `DECISIONS.md` / `STATUS.md`: Full architectural log and stage progress.
  - `concepts.yaml`: 16 canonical concepts covering Anchor, TS wallet precision, and security smells.

- **Source Code (`src/emc/`)**:
  - `cli.py`: Typer CLI wiring (`init`, `quiz`, `detect`, `generate`, `eval`, `report`, `review`, `hook`, `doctor`, `config`).
  - `detect/`:
    - `models.py`: Severity weights (CRITICAL=10.0, HIGH=5.0, MEDIUM=2.5, LOW=1.0, INFO=0.5).
    - `rust_anchor.py`: 8 Anchor static inspection rules (missing signer, unchecked account, unchecked arithmetic, PDA seeds, invoke_signed, close/realloc, remaining_accounts, unverified CPI).
    - `ts_wallet.py`: 4 TS rules (lamport units, base decimal scaling, address validation, hardcoded RPCs).
    - `generic.py`: 4 generic smells (bypass flags, sensitive logging, insecure fallback, empty catch).
    - `ranking.py`: Hunk risk ranking with multiplier weights.
    - `engine.py` & `taxonomy.py`: Detection orchestration and concepts parser.
  - `ingest/`:
    - `diff.py`: Structured hunk splitting, 1-indexed line mapping (`DiffLine`, `DiffHunk`, `FileDiff`).
    - `filter.py`: `.emcignore` and lockfile filtering.
  - `redact/`:
    - `engine.py`: Secret scanner and redaction engine.
    - `bip39_words.py`: Wordlist for mnemonic seed phrase detection.
    - `rules.py` & `models.py`: Regex and token patterns for private keys and credentials.
  - `llm/`:
    - `provider.py`: `LLMProvider`, `AnthropicProvider`, `FakeProvider`, `LocalProvider`.
    - `cache.py`: `DiskCache` under `.emc/cache/` keyed by `sha256(diff_hash : model : sha256(prompt))` with cost tracking.
  - `questions/`:
    - `schema.py`: 5 question types (`predict-output`, `what-breaks-if`, `consequence`, `spot-the-bug`, `explain-back`).
    - `generator.py`: Structured generation pipeline with single-retry recovery.
    - `validate.py`: 4-step quality gate (grounding, leakage, solvability, ambiguity).
  - `grade/`:
    - `models.py`: `GradeResult`, `ScoreBreakdown`, `RubricEvaluation`.
    - `deterministic.py`: Numeric and key option matching with distractor collision defense.
    - `rubric.py`: LLM rubric judge with deterministic fallback.
  - `session/`:
    - `runner.py`: Interactive session loop with hint ladder (-25% per hint).
    - `display.py`: Rich terminal syntax-highlighted diff rendering.
  - `ledger/`:
    - `models.py` & `storage.py`: Thread-safe append-only ledger (`.emc/ledger.jsonl`) with cross-process OS locking.
    - `tracker.py`: Leitner 5-box mastery state machine.
    - `report.py` & `review.py`: Mastery progress reporting and weak-concept replay quiz engine.
  - `gate/`:
    - `evaluator.py`: Gating verdicts (`off`, `warn`, `gate`).
    - `trailer.py`: Git commit trailer formatter and injection.
  - `hooks/`:
    - `manager.py`: Git hook installer with foreign hook protection and backup.
  - `eval/`:
    - `runner.py`: Automated eval benchmark engine (`emc eval`).
    - `mutation.py`: Programmatic bug injector across 11 vulnerability categories.
    - `ablation.py`: Comparative ablation engine vs naive single-prompt baseline.

- **Test Suite (`tests/`) - 281 Passing Tests**:
  - `test_detectors.py`, `test_edge_cases.py`, `test_ranking.py`, `test_taxonomy.py`
  - `test_ingest.py`, `test_redact.py`, `test_injection.py`
  - `test_llm.py`, `test_cache.py`, `test_questions.py`, `test_rejection_paths.py`
  - `test_session.py`, `test_grade.py`, `test_ledger.py`, `test_gate.py`, `test_hooks.py`
  - `test_eval.py`, `test_doctor.py`, `test_cli.py`, `test_cli_detect.py`, `test_cli_dry_run.py`, `test_cli_stage3.py`

- **Benchmark Dataset (`fixtures/eval/`)**:
  - 31 seeded vulnerabilities (21 Anchor Rust, 10 TypeScript) in `manifest.json`.
  - 30 hand-labeled free-text rubric grading evaluations in `free_text_rubric.json`.
  - Empirical report published at `docs/EVAL.md`.

---

## 5. Benchmark Performance Highlights
- **Seeded-Bug Surfacing Rate**: **100.0%** (31/31) [Baseline Naive: 12.9%]
- **Grounded-Question Rate**: **100.0%** [Baseline Naive: 0.0%]
- **Secret Redaction Recall**: **100.0%** (17/17 secrets blocked) [Baseline Naive: 0%]
- **Injection-Resistance Rate**: **100.0%** (5/5 prompt injections neutralized) [Baseline Naive: 0%]
- **Grader Agreement**: **96.7% accuracy, 93.3% precision, 100.0% recall, 96.6% F1**
- **Average Cost per Session**: **$0.0018 USD**
- **Total Pipeline Latency**: **36.3 ms**

---

## 6. How to Run & Verify
```bash
# Navigate to project root
cd c:\Users\TEJAS\Downloads\resume\explain-my-own-code

# Run all 281 tests
pytest

# Run linter & static type checks
ruff check .
mypy src tests

# Run Stage 7 Benchmark Evaluation Suite
python -m emc.cli eval --ablation --output docs/EVAL.md
```
