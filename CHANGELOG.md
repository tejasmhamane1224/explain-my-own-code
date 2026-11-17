# Changelog

All notable changes to `explain-my-own-code` (`emc`) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-11-17

### Added
- **Structured Diff Ingestion (`emc.ingest`)**:
  - Structured hunk parser with exact 1-indexed line mapping (`DiffLine`, `DiffHunk`, `FileDiff`).
  - `.emcignore` pattern support, binary file skipping, and lockfile filtering.
  - Configurable file count and diff byte caps preventing context bloat.
- **Local Secret Redaction (`emc.redact`)**:
  - Local-first pre-transmission scanner with 100% recall on secrets fixture set.
  - Redaction rules for Solana Base58 private keys, Solana keypair byte arrays, EVM hex keys, BIP-39 12/24-word seed phrases, API credentials (Anthropic, OpenAI, Google, AWS, GitHub, HuggingFace), and `.env` variables.
  - Cryptographic token masking with sha256 hash digests.
- **Prompt Injection Defense (`emc.ingest`, `emc.questions`)**:
  - Untrusted diff quarantine delimiters (`<untrusted_diff_payload>`).
  - System override instruction scanner neutralizing adversarial comments.
- **Deterministic Static Detectors (`emc.detect`)**:
  - 8 Anchor Rust rules: missing signer, unchecked accounts without safety comments, unchecked raw arithmetic, PDA seed bump validation, improper invoke_signed seeds, close/realloc init safety, dynamic remaining_accounts checks, and unverified CPI programs.
  - 4 TypeScript wallet rules: lamport/SOL mixing, token decimal base unit omissions, dynamic PublicKey validation, and hardcoded mainnet RPC endpoints.
  - 4 Generic code smells: security bypass flags, sensitive credential logging, insecure fallback credentials, and empty catch/except blocks.
  - Multi-factor hunk risk ranking engine combining severity weights, line churn, and file importance multipliers.
- **LLM Layer & Disk Cache (`emc.llm`)**:
  - Abstract `LLMProvider` supporting Anthropic Claude, `FakeProvider`, and `LocalProvider`.
  - Content-hashed filesystem cache under `.emc/cache/` keyed by `sha256(diff_hash : model : prompt)`.
  - Enforced per-session token budgets and `--max-cost` limits.
- **4-Step Question Quality Gate (`emc.questions`)**:
  - 5 canonical question types: `predict-output`, `what-breaks-if`, `consequence`, `spot-the-bug`, `explain-back`.
  - Automated 4-step quality gate: snippet grounding check, no answer leak check, automated solver pass, and ambiguity check.
  - Single-retry regeneration recovery for failed candidate questions.
- **Interactive Terminal Quiz & Hybrid Grading (`emc.session`, `emc.grade`)**:
  - Rich terminal quiz UI with syntax-highlighted diffs, hint ladder (-25% per hint), skip, and quit controls.
  - Deterministic key/numeric/line matching with distractor collision defense.
  - Multi-criteria rubric judge for free-text responses with deterministic keyword fallback.
- **Leitner 5-Box Mastery Ledger (`emc.ledger`)**:
  - Thread-safe append-only storage at `.emc/ledger.jsonl` with cross-process OS locking (`msvcrt`/`fcntl`).
  - Leitner 5-box spaced repetition tracking with promotion on success and demotion to Box 1 on failure.
  - `emc report` command with encoding-safe Leitner progress indicators and weak concept alerts.
  - `emc review` command for targeted spaced-repetition replays on weak concepts.
- **Commit Gating & Git Hooks (`emc.gate`, `emc.hooks`)**:
  - Operational modes: `off` (audit only), `warn` (alert on failure), and `gate` (block commit on failure).
  - Git commit trailer injection (`Comprehension: 4/5`).
  - Idempotent git hook installer with foreign hook protection and automated `.emc.bak` backup/restore.
  - CI and non-TTY automatic bypass preventing pipeline hangs.
- **Evaluation Benchmark Suite (`emc.eval`)**:
  - `emc eval` benchmark runner testing 31 seeded vulnerabilities and 30 hand-labeled free-text evaluations.
  - Comparative ablation study demonstrating +87.1% bug surfacing advantage over naive single-prompt baseline.
  - Automated report generation outputting to `docs/EVAL.md`.
- **Documentation & Security (`docs/`, root)**:
  - Comprehensive `README.md` with 10-dimension competitor matrix and 60-second quickstart.
  - STRIDE threat model (`docs/THREAT_MODEL.md`).
  - Coordinated vulnerability disclosure policy (`SECURITY.md`).
  - Contributor guidelines (`CONTRIBUTING.md`).
