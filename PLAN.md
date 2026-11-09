# Master Implementation Plan: explain-my-own-code (`emc`)

## 1. Executive Summary
`emc` is an open-source developer tool designed to verify that engineers truly comprehend the code they commit, especially when using generative AI tools (Cursor, Copilot, Claude Code). Unlike generic quiz tools that ask superficial questions about raw diffs, `emc` operates on high-risk domains—specifically Solana/Anchor (Rust) and TypeScript wallet integrations—where subtle misunderstandings lead directly to catastrophic losses of funds.

---

## 2. Competitor Analysis & Honest Differentiation

| Dimension | `arivcode` | `bel-ai-jar` | `cognit` | Generic Claude Quiz Skills | `emc` (explain-my-own-code) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Domain-Aware Detectors** | None (pure LLM) | AST heuristics for Python | None | None | **Dedicated deterministic Solana/Anchor & TS wallet risk rules** |
| **Snippet Grounding** | Loose prompt request | Often quotes out-of-context | LLM summary | High hallucination risk | **Strict validation gate**: line-for-line exact diff snippet matching |
| **Question Types** | Multiple Choice only | MC & True/False | Flashcards | Free-form chat | **5 Types**: predict-output, what-breaks-if, consequence (funds at risk), spot-the-bug (injected mutant), explain-back (rubric judged) |
| **Question Quality Gate** | None | Basic JSON parse | None | None | **4-Step Gate**: diff existence, no answer leak, independent solvability pass, ambiguity detection |
| **Prompt Injection Defense**| Fragile system prompt | Unchecked diff feed | None | None | **Data-block isolation, schema constraint, non-code rejection, injection test suite** |
| **Secret Redaction** | Basic regex | None | None | Dependent on LLM | **Local-first multi-pattern scanner**: Base58 keypairs, hex privkeys, seed phrases, env secrets with `--dry-run` |
| **Grading Philosophy** | Exact string / token | Exact string | Subjective LLM | Chat agreement | **Hybrid**: Deterministic grading for MC/predict; Rubric-based LLM judge with few-shot calibration for free-text |
| **Mastery Tracking** | Global score | Session history | Basic spaced repetition | None | **Concept Leitner boxes** (`.emc/ledger.jsonl`), review missed concepts |
| **Evaluation & Benchmark** | Anecdotal | None | None | None | **Reproducible `emc eval`**: 30+ seeded bug diffs, naive baseline ablation |
| **Git Integration** | Standalone script | Git alias | Standalone app | None | **Git pre-commit gate**, CI non-interactive safe mode, "Comprehension: X/Y" trailers |

---

## 3. High-Level Architecture & Pipeline

```
           [ Git Diff / Staged / Commit / Stdin ]
                             │
                             ▼
                  ┌──────────────────────┐
                  │   1. INGEST & SPLIT  │ (hunk extraction, line index)
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │  2. SECRET REDACTION │ (base58, hex keys, seed phrases, envs)
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │ 3. STATIC DETECTORS  │ (Anchor: missing signer, unchecked account, PDA bump)
                  └──────────┬───────────┘ (TS: lamport math, base units, RPC endpoints)
                             │
                             ▼
                  ┌──────────────────────┐
                  │   4. RANK & PLAN     │ (rank hunks by risk, assign question templates)
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │ 5. GENERATE (SCHEMA) │ (structured JSON schema via LLM provider)
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │  6. VALIDATION GATE  │ (grounding check, leak check, solvability, ambiguity)
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │  7. SESSION & QUIZ   │ (Rich TTY UI, hint ladders, answer input)
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │ 8. GRADE & FEEDBACK  │ (deterministic + rubric judge for free text)
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │  9. LEDGER & OUTPUT  │ (Leitner boxes in .emc/ledger.jsonl, trailers, exit code)
                  └──────────────────────┘
```

---

## 4. Question Types & Quality Gate

### Question Types
1. **`predict-output`**: What will this hunk return or mutate given state X?
2. **`what-breaks-if`**: If input Y is passed or parameter Z is omitted, what failure occurs?
3. **`consequence`**: Specifically for smart contracts and wallet transfers: what happens to user funds or authorization?
4. **`spot-the-bug`**: Injects a realistic flaw into a clone of the diff snippet and asks the developer to identify the security bug.
5. **`explain-back`**: Free-text prompt where the developer explains why a pattern was chosen; evaluated using a structured multi-criteria rubric.

### 4-Stage Quality Gate
Before a question reaches the user, it must pass all 4 checks:
1. **Diff Grounding**: Every line number and code snippet cited must exist verbatim in the analyzed diff.
2. **No Answer Leakage**: The correct answer key cannot appear verbatim in the prompt or distractor options.
3. **Independent Solvability**: An automated solver pass given only the diff must reproduce the expected answer key.
4. **Ambiguity Check**: Distractors are tested against alternative valid interpretations; flagged if multiple choices are defensible.

---

## 5. Leitner Mastery Tracking (`concepts.yaml`)
Concepts are organized hierarchically:
- `anchor.signer_check`: Verification of account signers and authorities.
- `anchor.pda_seeds`: Canonical PDA seed derivation, bump constraints, and seeds constraints.
- `anchor.account_types`: Use of `AccountInfo` vs `UncheckedAccount` vs `Account<'info, T>`.
- `anchor.realloc_close`: Rent exemption, account zeroing, and close target security.
- `math.checked_arith`: Prevention of integer overflow/underflow in smart contract balance logic.
- `ts.lamport_units`: Conversion between SOL and lamports (10^9) and SPL token decimals.
- `ts.address_validation`: PublicKey checksums, system program checks, and off-curve addresses.
- `async.race_conditions`: Nonce handling, blockhash expiration, transaction re-ordering.

Each concept maintains a Leitner box (1 to 5) in `.emc/ledger.jsonl`. Correct answers advance the concept; incorrect answers reset or demote it.

---

## 6. Stage-by-Stage Implementation Roadmap

### Stage 0: Plan + Scaffold [CURRENT]
- Repository structure, `pyproject.toml`, `.gitignore`, CI workflow (`.github/workflows/ci.yml`).
- Core documentation: `CLAUDE.md`, `PLAN.md`, `DECISIONS.md`, `STATUS.md`.
- Basic Typer CLI app with `emc --help` and `emc doctor`.
- `emc doctor` diagnostics: git checks, API key status, model configuration, python runtime.
- Verification: pytest passes, ruff passes, mypy passes.

### Stage 1: Ingest + Redact + Injection Fixtures [COMPLETED]
- Git diff parsers (staged, commit ranges, stdin) with precise 1-indexed line mapping (`DiffLine`, `DiffHunk`, `FileDiff`).
- `.emcignore` and default lockfile / build asset filtering via `pathspec`.
- Configurable file-size and diff-size caps preventing context explosion.
- Secret redaction engine (7 rules: Solana keypair arrays, Base58 keys, EVM hex keys, BIP-39 seed phrases, API keys, .env values, generic credentials) with 100% recall on secrets fixture set.
- Untrusted diff data encapsulation and delimiter collision sanitization.
- Adversarial prompt injection fixture suite (`fixtures/injections/`) testing 5 injection vectors.
- `emc quiz --dry-run` flag outputting Rich summary table, detected secrets table with masked previews, and sanitized diff payload.
- Comprehensive test suite (49 passing tests, clean ruff and mypy).

### Stage 2: Detectors + Ranking (No LLM) [COMPLETED]
- Deterministic static risk rules across 3 domain suites:
  - `rust_anchor`: 8 rules (missing Signer / has_one, UncheckedAccount without safety comment, unchecked arithmetic, PDA seeds bump verification, improper invoke_signed seeds, close/realloc configuration, remaining_accounts checks, unverified CPI program id).
  - `ts_wallet`: 4 rules (mixing SOL and lamports / float balance math, base units vs human units in token instructions, dynamic PublicKey address validation, hardcoded production RPC endpoints).
  - `generic`: 4 rules (security bypass flags, sensitive credential logging, insecure fallback credentials, empty catch/except error swallowing).
- Concepts taxonomy loaded from `concepts.yaml` (`src/emc/concepts.yaml`) with 16 registered mastery concepts.
- Multi-factor hunk risk ranking engine (`src/emc/detect/ranking.py`) combining rule severity weights, additions/deletions change volume, and file importance multipliers (Smart contracts 1.8x, Wallet/Auth 1.5x, Standard 1.0x, Docs/Tests 0.3x).
- Positive and negative fixture suite (`fixtures/detectors/`) covering all 16 rules (32 unified diff fixtures) with 100% true-positive recall and 0% false positives.
- `emc detect` and `emc quiz --dry-run` terminal integration rendering Detected Static Risk Findings and Ranked Diff Hunks Rich tables.
- Comprehensive test suite (100 passing tests, clean ruff and strict mypy).

### Stage 3: LLM Layer + Generation + Validator [COMPLETED]
- Abstract provider interface `LLMProvider` with token usage and cost accounting.
- `AnthropicProvider` (Claude 3.7/3.5 Messages API with tool-use JSON schema and published pricing).
- `FakeProvider` (configurable deterministic responses, scripted handlers, queueing, and budget simulation).
- `LocalProvider` (HTTP stub for local models like Ollama or llama.cpp).
- Content-hash `DiskCache` under `.emc/cache/` keyed by `sha256(diff_hash : model : sha256(prompt))` with `--max-cost` and token budget protection.
- 5 Canonical question types (`predict-output`, `what-breaks-if`, `consequence`, `spot-the-bug`, `explain-back`) and Pydantic schemas.
- Question planner mapping static detector findings and open hunks to targeted question templates.
- 4-step Question Validator (`snippet_grounding`, `no_answer_leak`, `independent_solvability`, `non_ambiguity`, `injection_instruction`) with single-retry regeneration and rejection logging.
- `emc generate` and `emc quiz --dry-run --generate` CLI commands with Rich table and JSON output.
- Comprehensive acceptance tests covering every rejection path (162 passing tests).

### Stage 4: Session + Grading
- Interactive Rich terminal UI.
- Hint ladder (revealing hints deducts score points).
- Hybrid grading (deterministic match + rubric LLM judge for free text).

### Stage 5: Ledger + Mastery + Report/Review
- `.emc/ledger.jsonl` storage with Leitner box algorithm.
- `emc report`: Visual summary of concept masteries and weak areas.
- `emc review`: Spaced repetition session targeting previously failed concepts.

### Stage 6: Modes, Gate, Hooks, CI-Safe Behavior
- `.emc.toml` configuration parser.
- Modes: `off`, `warn`, `gate`.
- Git pre-commit and post-commit hook installers.
- Commit trailer injection ("Comprehension: 4/5").
- Non-interactive and CI detection (no-TTY bypass).

### Stage 7: Evaluation Suite (`emc eval`)
- 30+ seeded-bug diffs (20 Anchor Rust, 10 TS).
- Grounded-question rate, bug surfacing rate, redaction recall, injection resistance metrics.
- Baseline ablation comparison against naive one-shot quiz prompt.
- Generation of `docs/EVAL.md`.

### Stage 8: Documentation & Security Hardening
- Comprehensive README with problem statement, 60-second demo, honest comparison table.
- Threat model documentation and `SECURITY.md`.
- `CONTRIBUTING.md` guidelines.

### Stage 9: Release Readiness
- Version stamping, changelog generation.
- Packaging verification (`pipx`, PyPI dry-run).
- Matrix testing across Python versions.
