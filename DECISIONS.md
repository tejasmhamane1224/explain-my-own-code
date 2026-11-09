# Architectural Decision Records (ADRs)

## ADR-000: Independent Project Isolation
- **Status**: Accepted
- **Context**: The root workspace contains personal files, resumes, and diverse repositories (`circuit-pay`, `jupiter-redesign`, etc.).
- **Decision**: Scaffold `explain-my-own-code` as a standalone git repository in its own directory, ensuring clean version control, isolated dependencies, and professional packaging without pollution from parent directories.

## ADR-001: CLI Framework Choice (Typer + Rich)
- **Status**: Accepted
- **Context**: The CLI requires rich terminal rendering (tables, panels, status checks, diff highlights, hint ladders) as well as non-interactive CI safety.
- **Decision**: Use Typer (backed by Click) with Rich. Typer provides clean type-hinted command definitions, and Rich gives fine-grained control over colors, tables, and progress without external terminal quirks.

## ADR-002: Deterministic Detectors Preceding LLM Planning
- **Status**: Accepted
- **Context**: Pure LLM diff analysis suffers from hallucination, high latency, token cost, and inconsistent detection of critical smart contract security bugs (e.g. missing Anchor `Signer` check or lamport decimal mismatches).
- **Decision**: Run fast deterministic static analysis detectors first (Rust Anchor rules, TS wallet rules, generic rules). The question planner uses detector outputs to select targeted question templates before falling back to LLM for open questions.

## ADR-003: Strict 4-Stage Question Quality Gate
- **Status**: Accepted
- **Context**: Poorly formed or hallucinated questions undermine developer trust and measure knowledge of nonexistent code.
- **Decision**: Every generated question must pass a rigorous 4-stage validator:
  1. Exact line and snippet grounding against the input diff.
  2. Verification that the answer key is not leaked in the question or options.
  3. Independent solver pass to ensure the question is solvable purely from the diff.
  4. Ambiguity analysis to reject questions with multiple defensible answers.

## ADR-004: Untrusted Diff Input & Prompt Injection Defense
- **Status**: Accepted
- **Context**: Git diffs can contain malicious instructions intended to hijack the LLM evaluator (indirect prompt injection via code comments or string literals).
- **Decision**:
  1. Diffs are strictly wrapped inside designated untrusted data blocks.
  2. System prompts instruct the LLM to treat diff contents solely as inert data.
  3. LLM responses are enforced via rigid Pydantic JSON schemas.
  4. Any model output containing system instructions, ungrounded code, or external URLs is rejected.

## ADR-005: Local-First Secret Redaction
- **Status**: Accepted
- **Context**: Developers frequently stage or commit files containing sensitive tokens, Solana private keys, seed phrases, or `.env` secrets.
- **Decision**: All diffs are scanned and redacted locally before any data is sent to external LLM providers. Provide `--dry-run` to allow developers to inspect the exact redacted diff before network transmission.

## ADR-006: Diagnostic Doctor Architecture
- **Status**: Accepted
- **Context**: Developers running `emc` may face misconfigured git setups, missing Anthropic keys, or incorrect Python environments.
- **Decision**: Implement `emc doctor` as a standalone diagnostic module checking:
  - Git installation and repository status.
  - Anthropic API key detection (safely masked).
  - Configured LLM model (`EMC_MODEL` or default).
  - `.emc.toml` configuration status.
  - Python runtime environment.
  Doctor returns exit code 0 when all critical checks pass, providing clean visual Rich status tables.

## ADR-007: Structured Hunk Ingestion with Precise 1-Indexed Line Mapping
- **Status**: Accepted
- **Context**: The Question Quality Gate requires grounding questions on verifiable line numbers and verbatim code snippets. Passing raw diff strings to LLMs leads to hallucinated line numbers and ungrounded questions.
- **Decision**: Ingest git diffs (staged, commit range, stdin) into strict Pydantic structures (`FileDiff`, `DiffHunk`, `DiffLine`). Each line maintains `old_line_number`, `new_line_number`, diff marker (`+`, `-`, ` `), and trimmed content. Support `.emcignore` path filtering and byte/hunk caps to prevent memory bloat or context blowout.

## ADR-008: Multi-Pattern Local Secret Redaction Engine
- **Status**: Accepted
- **Context**: Sending raw diffs to remote LLM providers risks exposing high-value crypto keys, cloud credentials, or seed phrases.
- **Decision**: Scan diffs before any network transmission across 7 distinct secret classes:
  1. Solana keypair byte arrays (32 or 64 bytes in JSON, Rust `vec!`, or TypeScript `Uint8Array`).
  2. Solana Base58 private keys (standalone 87-88 chars and assigned 43-88 chars).
  3. 64-character EVM / hex private keys (0x-prefixed and assigned).
  4. BIP-39 mnemonic seed phrases (12, 15, 18, 21, 24 words validated against full 2048-word English dictionary with hyphen/comment boundary protection).
  5. API tokens (Anthropic, OpenAI, GitHub PAT, AWS Key/Secret, Stripe, Slack, Solana RPC).
  6. `.env` variable secret assignments.
  7. High-entropy generic secret assignments.
  Replace secrets with typed tokens (e.g. `[REDACTED:solana_keypair_array]`) while preserving diff syntax and line boundaries. Provide safe masking for inspection.

## ADR-009: Untrusted Data Framing and Delimiter Collision Neutralization
- **Status**: Accepted
- **Context**: Attackers can embed indirect prompt injections in code comments, docstrings, or test variables designed to hijack the LLM evaluator, override grading, or leak system prompts.
- **Decision**: Wrap all untrusted diff text inside bounded delimiters (`<<<UNTRUSTED_DIFF_PAYLOAD>>>`). Sanitize and escape any occurrence of payload boundary markers inside the diff. Frame all content explicitly as passive, inert data never to be executed or followed as instructions. Scan diffs for known prompt injection signatures.

## ADR-010: Deterministic Smart Contract & Wallet Risk Detection Rules
- **Status**: Accepted
- **Context**: Pure LLM reasoning about high-risk Solana/Anchor and TS wallet diffs is probabilistic, slow, and prone to overlooking subtle security flaws (e.g. missing signer checks, unscaled token decimals, unchecked arithmetic).
- **Decision**: Implement fast deterministic static analysis rules across 3 domain suites:
  1. `rust_anchor`: 8 rules (missing Signer / has_one, UncheckedAccount without safety comment, unchecked arithmetic, PDA seeds bump verification, improper invoke_signed seeds, close/realloc configuration, remaining_accounts checks, unverified CPI program id).
  2. `ts_wallet`: 4 rules (mixing SOL and lamports / float balance math, base units vs human units in token instructions, dynamic PublicKey address validation, hardcoded production RPC endpoints).
  3. `generic`: 4 rules (security bypass flags, sensitive credential logging, insecure fallback credentials, empty catch/except error swallowing).
  Every rule is backed by positive and negative fixtures verifying 100% true-positive recall and 0% false-positive rate.

## ADR-011: Multi-Factor Diff Hunk Risk Ranking Engine
- **Status**: Accepted
- **Context**: A pull request or commit diff may contain dozens of hunks across documentation, tests, configuration, and core logic. Asking developers random questions dilutes attention from the most dangerous code lines.
- **Decision**: Score and rank each diff hunk using a multi-factor risk formula:
  `Risk Score = (Finding Severity Weights + (Additions * 0.1 + Deletions * 0.03)) * File Multiplier`
  Where findings carry severity weights (CRITICAL: 10.0, HIGH: 5.0, MEDIUM: 2.5, LOW: 1.0), additions carry 3.3x more risk weight than deletions, and file importance applies domain multipliers (Smart Contracts: 1.8x, Wallet/Auth: 1.5x, Standard Code: 1.0x, Tests/Docs: 0.3x). Question planning prioritizes the highest-ranked hunks.

## ADR-012: Multiline Attribute Balancing, Bidirectional Matching, and OS Path Normalization
- **Status**: Accepted
- **Context**: Real-world Rust/Anchor and TypeScript code heavily utilizes multiline formatting (e.g. rustfmt multi-line `#[account(...)]` attributes, multiline instruction calls, and method calls like `user.key().as_ref()` in seed slices). Naive single-line regex matching yields false positives on valid code and false negatives on multi-line statements.
- **Decision**:
  1. Attribute Balance Tracking: Parse multi-line Anchor `#[account(...)]` blocks using parenthesis balance counters, guaranteeing that inner method calls (e.g. `.as_ref()`) do not prematurely terminate attribute blocks.
  2. Protocol-Safe Comment Stripping: Strip inline comments using negative lookbehinds (`(?<!:)//`) to preserve `https://` URLs in hardcoded RPC detectors.
  3. Bidirectional Precision Matching: Check arithmetic operators bidirectionally (`float * balance` and `balance * float`, `sol + balance` and `balance + sol`).
  4. Path Normalization: Normalize Windows backslashes (`\`) to forward slashes (`/`) before regex evaluation and dictionary key lookups in hunk ranking.

## ADR-013: LLM Provider Abstraction, Deterministic Fake Provider, and Local Stub
- **Status**: Accepted
- **Context**: Relying directly on vendor SDKs introduces tight coupling, network dependency during tests, unpredictable costs, and prevents offline local development.
- **Decision**: Define an abstract `LLMProvider` contract providing `generate_text` and `generate_structured` (Pydantic schema validation). Implement three concrete providers:
  1. `AnthropicProvider`: Production client using Anthropic Messages API with structured Tool-Use, model configuration from `EMC_MODEL` (default: `claude-3-7-sonnet-latest`), and published pricing tables for cost tracking.
  2. `FakeProvider`: Deterministic, scriptable provider supporting canned queues, custom handlers, simulated exceptions, and token estimation (~4 chars/token) for unit tests and CI.
  3. `LocalProvider`: HTTP stub supporting Ollama, llama.cpp, or local servers with JSON schema constraints.
  Enforce token budgets and max-cost ceilings natively within provider base classes.

## ADR-014: Deterministic Disk-Backed Semantic Cache Keying
- **Status**: Accepted
- **Context**: Re-running comprehension checks or evaluating diffs repeatedly without caching incurs redundant LLM costs, introduces latency, and impairs reproducibility.
- **Decision**: Implement `DiskCache` storing structured responses under `.emc/cache/` (or configured directory). Compute cache keys using:
  `Key = sha256(diff_hash : model : sha256(prompt))`
  Cached responses return with zero cost (`cost_usd = 0.0`) and bypass network calls completely. Support cache invalidation via `clear()` and cache inspection.

## ADR-015: 5 Canonical Comprehension Question Types and Pydantic Schemas
- **Status**: Accepted
- **Context**: Generic flashcards or single multiple-choice formats fail to evaluate deep comprehension of safety-critical Solana smart contract and wallet code.
- **Decision**: Standardize on 5 canonical question types:
  1. `predict-output`: Compute state mutation or return value for input state X.
  2. `what-breaks-if`: Analyze edge cases, omissions, or malicious inputs.
  3. `consequence`: Trace user funds, signer authorization, or protocol solvency.
  4. `spot-the-bug`: Present a mutated snippet with an injected flaw and ask the developer to identify the vulnerability.
  5. `explain-back`: Free-text justification evaluated against structured multi-criteria rubrics (`RubricCriterion`).
  Model all questions, distractors, rubrics, and hint ladders as rigid Pydantic models.

## ADR-016: Rigorous 4-Step Quality Gate with Single-Retry Self-Correction
- **Status**: Accepted
- **Context**: LLM hallucination in question generation generates bogus line references, leaks answers in question stems, creates unsolvable questions, or falls prey to indirect prompt injections.
- **Decision**: Filter all candidate questions through an automated 4-step quality gate:
  1. `snippet_grounding`: Verbatim code snippet existence and exact line range coverage in diff hunks.
  2. `no_answer_leak`: Regex and phrase scanning ensuring neither the letter key nor the substantive answer text leaks in the stem or distractor explanations.
  3. `independent_solvability`: Automated solver pass with diff alone reproducing the expected answer key.
  4. `non_ambiguity`: Ambiguity evaluation pass flagging questions with multiple defensible choices.
  5. `injection_instruction`: Rejection of instruction override patterns and unauthorized external URLs.
  If any check fails, provide structured feedback to the model and retry exactly once; if the second attempt fails, drop the question and log the rejection reason.

## ADR-017: Quality Gate Hardening, Contiguous Hunk Validation, and Cache-First Budget Lifecycle
- **Status**: Accepted
- **Context**: In review of Stage 3, multiple subtle vulnerabilities were discovered:
  1. Snippet grounding used naive `zip(snippet_lines, hunk_range_lines)` without line-count equivalence, permitting out-of-bounds line ranges (e.g., 10..10000) or extra unverified snippet lines to silently pass due to Python's `zip` truncating to the shorter iterable.
  2. Answer leakage checking tested only stems and `\bunlike\s+{key}\b` phrases, allowing distractor choices and distractor explanations to directly leak keys (e.g. "Choice B is correct").
  3. Prompt injection checks omitted untrusted diff encapsulation markers and comprehension flag tampering (`"comprehension_passed": true`).
  4. Cache lookups were blocked behind `check_budget()`, causing cache hits with zero dollar cost to fail when budget ceilings were reached.
  5. BudgetExceededError was swallowed as a generic ProviderError and triggered wasteful retries against an exhausted budget.
- **Decision**:
  1. Grounding: Require full contiguous line range coverage within a single hunk (`expected_range_set.issubset(...)`) and verify snippet lines match a contiguous windowed sub-sequence.
  2. Answer Leakage: Scan both question stem and all distractor fields/explanations for direct and indirect answer key patterns.
  3. Prompt Injection Defense: Expand injection patterns with delimiter collisions (`<<<END_UNTRUSTED_DIFF_PAYLOAD>>>`, `</system>`) and scoring manipulation flags.
  4. Cache Budget Priority: In `CachedLLMProvider`, perform cache check prior to `check_budget()` so cached responses ($0.00 cost) are served without tripping budget caps.
  5. Immediate Abort on Budget Exceeded: In `QuestionGenerator`, catch `BudgetExceededError` explicitly, log rejection reason `budget_exceeded`, and break retry loops immediately.

## ADR-018: Interactive Rich Terminal Quiz Loop, Progressive Hint Ladder Penalties, and Scriptable Session Driver
- **Status**: Accepted
- **Context**: Developers need an engaging, informative terminal experience during comprehension verification that visualizes diff context with syntax highlighting, provides progressive hints when stuck without giving away answers for free, and runs deterministically in automated CI/test environments without hanging on stdin.
- **Decision**:
  1. Rich UI Display: Render questions inside bordered Rich panels displaying file path, line numbers, concept badge, syntax-highlighted code snippet (monokai theme), spot-the-bug mutant highlights, choices, and hint count.
  2. Progressive Hint Ladder: Each question supports ordered hints (subtle -> specific -> near-complete). Revealing a hint deducts a fractional penalty (-25% per hint, capped at -75%), preserving developer agency while incentivizing independent reasoning.
  3. Scriptable Session Driver: `SessionRunner` accepts an optional `input_stream` (sequence or iterator). When provided, user inputs are read deterministically from the stream.
  4. CI & Non-TTY Bypass: In non-interactive environments (`CI=true` or `not sys.stdin.isatty()`), if no scripted input stream is provided, exit cleanly with code 0 and an informative notice rather than hanging waiting for user input.

## ADR-019: Hybrid Deterministic & Rubric-Based LLM Free-Text Grading with Offline Keyword Fallback
- **Status**: Accepted
- **Context**: Comprehension assessment requires grading both objective multiple-choice/spot-the-bug questions and subjective free-text `explain-back` justifications. Relying solely on LLMs introduces latency, non-determinism, and cost; relying solely on exact string matching fails on open-ended explanations.
- **Decision**:
  1. Deterministic Matcher: For multiple-choice, predict-output, consequence, and spot-the-bug questions, support exact key matching (case/punctuation-insensitive), numeric option indexing (1 -> A), full text matching, and line number extraction.
  2. Structured Rubric Judge: For `explain-back` questions, evaluate user explanations against predefined rubric criteria (`RubricCriterion`) using structured LLM output (`RubricEvaluationLLMOutput`), awarding itemized points and constructive feedback.
  3. Deterministic Offline Fallback: When LLM providers are unavailable or offline, evaluate rubric criteria deterministically using required taxonomy concepts and keyword stem set intersection, ensuring reliable testability and offline developer utility.

## ADR-020: Hardened Deterministic Matchers, Prompt Injection Rubric Defenses, and CLI JSON Contract Fidelity
- **Status**: Accepted
- **Context**: In review of Stage 4, several edge cases and contract vulnerabilities were identified:
  1. `deterministic_rubric_fallback` awarded 100% credit on criteria for arbitrary English inputs containing generic non-stopwords (e.g. "my bank account") or taxonomy framework prefixes (e.g. "anchor boat ship ocean" matched `anchor.missing_signer`).
  2. Free-text `explain-back` evaluations did not defend against adversarial prompt injections or override phrases in developer answers.
  3. `match_choice_key` did not resolve numeric choice phrases ("Option 1", "Choice 1") and suffered from substring collisions where typing an incorrect distractor text matched the correct choice if it was a substring.
  4. Spot-the-bug matching re-interpreted invalid choice selection numbers ("2" for Choice B) as line numbers if Choice A's text mentioned line 2.
  5. `emc quiz --json` violated the JSON contract by printing Rich text on `--skip`, CI bypass, empty diff, and errors.
- **Decision**:
  1. Rubric Hardening: Strip taxonomy namespace prefixes (`anchor.`, `ts.`, `math.`, `generic.`), require word-boundary regex matching for concept tokens, filter out rubric meta-words, and require substantive keyword overlap (>= 2 distinct domain keywords).
  2. Prompt Injection Defense: Scan developer explanations for prompt injection markers (`scan_for_injection_markers`) and evaluation overrides (`ignore previous instructions`, `passed: true`), failing immediately with zero score.
  3. Deterministic Matcher Disambiguation: Support "Option 1" / "Choice 1" numeric choices, check exact matches across all choices before partial matching, and reject ambiguous substrings matching multiple choices.
  4. Spot-the-bug Choice Index Protection: Treat numbers within `1..len(choices)` as choice selections, preventing fallthrough into line number matching.
  5. CLI JSON Contract: Guarantee valid JSON payloads on all exit paths when `--json` is enabled, and enforce `skip_allowed = false` configuration.

## ADR-021: Append-Only Event Ledger (.emc/ledger.jsonl) with Resilient Corrupted-Line Recovery
- **Status**: Accepted
- **Context**: Comprehension quiz outcomes must be tracked across git commits and developer sessions to model understanding over time. A relational database introduces heavy dependencies, binary file merge conflicts in git, and schema migration complexity. Furthermore, ledger files can become corrupted due to interrupted writes, external edits, or invalid JSON.
- **Decision**:
  1. JSON Lines Format: Store historical attempt events in `.emc/ledger.jsonl`, where each line is an independent, append-only JSON serialization of `LedgerEvent` (`timestamp`, `session_id`, `diff_hash`, `concept_id`, `question_type`, `user_answer`, `is_correct`, `hints_used`, `points_awarded`, `max_points`).
  2. In-Process Concurrency Control: Protect concurrent writes across threads via `threading.Lock()`, ensuring atomic line appends with immediate buffer flushing.
  3. Resilient Error Recovery: When parsing `ledger.jsonl`, read line-by-line and gracefully skip empty lines, malformed JSON strings, and schema validation errors without crashing or discarding valid neighboring records.

## ADR-022: Leitner 5-Box Concept Spaced Repetition Mastery Engine and Review Replay
- **Status**: Accepted
- **Context**: Developers need actionable visibility into knowledge gaps (e.g. repeated Anchor Signer oversights or TS unit scaling errors) and spaced repetition reinforcement targeting their weakest concepts.
- **Decision**:
  1. Leitner 5-Box Algorithm: Map concepts across 5 progressive mastery boxes (Box 1 = Weak/Novice, Box 2 = Developing, Box 3 = Competent, Box 4 = Proficient, Box 5 = Mastered). Correct answers advance the concept by 1 box (capped at 5); incorrect answers demote back to Box 1 and reset the current streak.
  2. Canonical Taxonomy Alignment: Initialize baseline concepts from `concepts.yaml` via `TaxonomyRegistry`, ensuring all 16 security and code health rules are tracked even before their first attempt.
  3. Weak Concept Prioritization: Order review candidates by failure severity: attempted Box 1 concepts with lowest pass rates first, followed by Box 2 developing concepts, followed by unreviewed concepts.
  4. Grounded Review Replay: Drive `emc review` sessions using verified detector diff fixtures and deterministic questions, automatically recording review session outcomes back into `.emc/ledger.jsonl` to advance developer mastery levels.
  5. Platform-Safe Visual Encoding: Adapt visual box progress bars (`[#####]` on cp1252 Windows consoles vs `[■■■□□]` on UTF-8 terminals) to prevent `UnicodeEncodeError` exceptions in legacy terminal environments.

## ADR-023: Inter-Process File Locking, Aborted Session Isolation, Quality Gate Review Grounding, and Review Completion Guard
- **Status**: Accepted
- **Context**: In reviewing Stage 5 implementation, several critical edge cases and contract vulnerabilities were identified:
  1. Process Concurrency: `_LEDGER_LOCK` only protected threads within the same Python process; independent CLI processes executing simultaneously could collide on append.
  2. Aborted Session Demotions: When a quiz or review session was aborted before all questions were answered, unattempted questions (`[aborted]`) were appended to the ledger as failures and demoted concepts to Box 1.
  3. Quality Gate Rejections on Review Questions: `build_review_question` used raw `hunk.content.strip()`, including diff prefix markers (`+`, `-`, ` `), causing review questions to fail `QuestionValidator` snippet grounding.
  4. Mastered Concept Review Replay Bug: `select_review_concepts` fell back to `all_masteries[:limit]` when no weak concepts existed (all Box >= 3 or Box 5), causing `emc review` to quiz users on mastered concepts and rendering the `no_weak_concepts` completion state unreachable.
  5. Subdirectory Path Drift: `quiz_cmd`, `report_cmd`, and `review_cmd` used relative `cfg.ledger_path` without resolving via `get_default_ledger_path()`, looking for ledger files inside subdirectories rather than repository root.
  6. CLI Input Validation: `emc review --limit 0` or negative limits and `emc report --category bogus` were silently accepted without error feedback.
- **Decision**:
  1. Inter-Process File Locking: Implement `_interprocess_lock` on `.emc/ledger.jsonl.lock` supporting `msvcrt.locking` on Windows and `fcntl.flock` on POSIX, guaranteeing process-safe atomic appends and reads.
  2. Aborted Attempt Filtering: Filter out `user_answer == "[aborted]"` from being written to `.emc/ledger.jsonl`, and ignore aborted events in `MasteryTracker.process_event`, protecting concept mastery.
  3. Verbatim Snippet Grounding: In `build_review_question`, extract verbatim code lines `[line_item.content for line_item in hunk.lines if line_item.line_type in ('+', ' ')]` and compute exact line ranges, ensuring review questions pass Quality Gate grounding.
  4. Safe Review Completion: In `select_review_concepts`, return an empty list when all concepts are competent/mastered (Box >= 3). Guard review execution before non-TTY bypass, reporting `"status": "no_weak_concepts"`.
  5. Root Ledger Resolution: Resolve ledger paths via `get_default_ledger_path()` across all CLI commands.
  6. Option Validation: Validate `--limit > 0` in `emc review` and `--category` against taxonomy in `emc report`.

## ADR-024: Operational Modes, Commit Gate Evaluation, Trailers, and Git Hooks Architecture
- **Status**: Accepted
- **Context**: Developers need configurable enforcement policies (`off`, `warn`, `gate`) across local workflows and CI pipelines, git commit comprehension trailers (`Comprehension: X/Y`), and safe, idempotent git hooks with foreign hook protection.
- **Decision**:
  1. Three-Tier Operational Modes (`src/emc/gate/evaluator.py`):
     - `off`: Comprehension check is disabled; logs structured skip audit event to `.emc/ledger.jsonl`, prints notice, and exits 0.
     - `warn`: Executes quiz; if score is below threshold, prints prominent warning banner but permits commit with exit 0.
     - `gate`: Executes quiz; if score is below threshold, displays blocking error banner and exits 1, halting git commit. Passing score exits 0.
  2. CI & Non-TTY Bypass Safety: Automatically detect `CI=true` or non-terminal environments and skip with exit 0 without hanging across all modes, while continuing to respect explicit scripted inputs (`--answers`).
  3. Commit Trailer Format and Injection (`src/emc/gate/trailer.py`):
     - Supports `fraction` (`Comprehension: 4/5`), `percentage` (`Comprehension: 80%`), and `detailed` (`Comprehension: 100% (anchor.signer_check: 2/2)`) trailer styles.
     - Staged trailer file (`.emc/last_trailer`) staged during `pre-commit` and consumed/unlinked during `commit-msg`.
     - Trailer injection places the trailer before trailing git comments (`#`), deduplicates existing trailers in place, and never modifies empty/aborted commit messages.
  4. Git Hooks Discovery & Foreign Hook Protection (`src/emc/hooks/manager.py`):
     - Discovers hooks directory using `git rev-parse --git-path hooks` with directory traversal fallbacks, fully supporting git worktrees, submodules, and subdirectories.
     - Detects existing foreign hooks and refuses to overwrite without `--force`. When `--force` is passed, automatically creates a backup (`.emc.bak`).
     - Uninstallation removes emc hooks and automatically restores the original foreign hook from backup if `.emc.bak` exists.
     - Idempotent: repeated `hook install` invocations detect existing emc markers and avoid duplicating scripts.

## ADR-025: Hardening Gate, Trailer Deduplication, Git Comment Characters, Hooks Path, and Session Abort Isolation
- **Status**: Accepted
- **Context**: Code review revealed seven robustness and behavioral risks:
  1. Trailer False Positives: Prefix matching on `Comprehension` matched regular commit body sentences (e.g. "Comprehension of this bug...").
  2. Blank Line Leak in Trailers: Repeated trailer deduplication accumulated blank lines between trailers and trailing comments.
  3. Git `core.commentChar`: Trailer placement hardcoded `#`, failing on repos with custom comment chars (`;`, `%`, etc.).
  4. Git `core.hooksPath`: Hooks manager needed explicit verification under custom hook directories configured via git.
  5. Foreign Hook Partial Actions: If `commit-msg` was foreign but `pre-commit` was not, uninstall/install could leave partially modified hooks.
  6. Aborted Session Phantom Demotions: `runner.py` used `user_answer="quit"`, escaping `[aborted]` filters and causing unattempted questions to demote Leitner boxes.
  7. Zero-Question Breakdown: Empty diffs evaluated against `evaluate_gate` risked blocking commits in `gate` mode.
- **Decision**:
  1. Explicit Trailer Colon: Extract prefix including colon (`prefix = f"{key}:"`), preventing false positives against prose.
  2. Blank Line Trimming: Always trim trailing blank lines before and after trailer insertion.
  3. Dynamic Comment Char: Detect `core.commentChar` via `git config --get core.commentChar` with fallback to `#`.
  4. Contiguous Trailers: Append trailers directly after existing trailers without intervening blank lines, adhering to `git interpret-trailers`.
  5. Upfront Foreign Hook Check: Validate all target hooks for foreign content upfront before mutating filesystem in `install_hooks` and `uninstall_hooks`.
  6. Aborted Question Tagging: Tag unreached questions in aborted sessions with `user_answer="[aborted]"`, and guard against both `[aborted]` and `quit` in `MasteryTracker` and CLI ledger logging.
  7. Zero-Question Pass: Allow 0-question breakdowns to pass cleanly in all gate modes.


