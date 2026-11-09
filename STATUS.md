# Project Status: explain-my-own-code (`emc`)

## Current Stage
**Stage 1: Ingest + Redact + Injection Fixtures** -- **COMPLETED & HARDENED**

---

## Stage Progress Checklist
- [x] **Stage 0: Plan + Scaffold**: Repo layout, `CLAUDE.md`, `PLAN.md` with competitor comparison, `DECISIONS.md`, `STATUS.md`, CI workflow, Typer/Rich CLI skeleton (`init`, `quiz`, `explain`, `report`, `review`, `eval`, `doctor`, `config`, `hook`), hardened `emc doctor` diagnostics with corrupted config detection & safe key masking, comprehensive unit tests (24 passed).
- [x] **Stage 1: Ingest + Redact + Injection Fixtures**: Git diff ingestion (staged `git diff --cached`, commit range `git diff <rev>`, stdin), structured hunk splitting with exact 1-indexed line mapping (`DiffLine`, `DiffHunk`, `FileDiff`), `.emcignore` and lockfile/asset path filtering, diff/file size caps, secret redaction engine (Solana keypair byte arrays, Solana Base58 private keys, EVM hex private keys, BIP-39 mnemonic phrases, API tokens including Google and HuggingFace, .env values, generic credentials) with 100% recall on secrets fixture set, untrusted diff encapsulation, prompt injection fixture suite (`fixtures/injections/`), `emc quiz --dry-run` displaying Rich summary, prompt injection warnings, and encapsulated redacted payload (57 tests passed).
- [ ] **Stage 2: Detectors + Ranking (No LLM)**: Solana/Anchor rules (missing Signer, UncheckedAccount, unchecked math, PDA bump), TS wallet rules (lamports/decimals, base units, RPCs), generic rules, hunk ranking.
- [ ] **Stage 3: LLM Layer + Generation + Validator**: Provider abstraction (Anthropic, Fake, Local), disk cache, question schemas, 4-step quality validator.
- [ ] **Stage 4: Session + Grading**: Interactive terminal quiz loop (Rich), hint ladder, deterministic matchers, LLM rubric judge for free text.
- [ ] **Stage 5: Ledger + Mastery + Report/Review**: `.emc/ledger.jsonl`, Leitner box mastery tracking, `emc report`, `emc review`.
- [ ] **Stage 6: Modes, Gate, Hooks, CI-Safe Behavior**: `.emc.toml` configuration, `off` / `warn` / `gate` modes, pre-commit hook installer, Comprehension trailer, CI bypass.
- [ ] **Stage 7: Evaluation Suite (`emc eval`)**: 30+ seeded diffs (20 Anchor, 10 TS), ablation vs naive single-prompt baseline, `docs/EVAL.md`.
- [ ] **Stage 8: Documentation & Security Hardening**: Comprehensive README with honest competitor matrix, threat model, `SECURITY.md`, `CONTRIBUTING.md`.
- [ ] **Stage 9: Release Readiness**: Packaging dry-run (`pipx`), changelog, versioning, GitHub Actions CI matrix.

---

## Stage 1 Deliverables Summary
1. **Diff Ingestion & Parsing (`src/emc/ingest/`)**:
   - `models.py`: Pydantic models `DiffLine`, `DiffHunk`, `FileDiff`, and `IngestResult` tracking 1-indexed line numbers (`old_line_number`, `new_line_number`), line types (`+`, `-`, ` `), and hunk headers.
   - `parser.py`: Robust unified diff parser supporting file additions, deletions, renames, binary diffs, quoted/space-separated file paths, and context lines.
   - `ignore.py`: Path filtering utilizing `.emcignore` and default ignore rules (lockfiles, minified JS/CSS, images, build artifacts) via `pathspec`.
   - `caps.py`: Diff size, single-file byte limit, and total hunk count limits preventing context blowouts, while preserving non-hunk file metadata (renames/mode changes).
   - `git.py`: Orchestrator retrieving staged diffs (`git diff --cached`), commit diffs (`git diff <rev>`, supporting both root and regular commits via `git show`), and stdin streams with UTF-8 decoding and safe process execution (`shell=False`).
   - `untrusted.py`: Untrusted diff framing inside bounded safety tags (`<<<UNTRUSTED_DIFF_PAYLOAD>>>`), escaping boundary collisions and scanning for prompt injection signatures.
2. **Secret Redaction Engine (`src/emc/redact/`)**:
   - `bip39_words.py`: Complete embedded 2048-word BIP-39 English wordlist.
   - `models.py`: `RedactionFinding` and `RedactionResult` tracking secret categories, line numbers, character spans, and safe masked previews.
   - `rules.py`: Scanners for:
     1. Solana keypair byte arrays (32/64 items, JSON/Rust `vec!`/Go `[]byte{}`/TS formats, decimal or hex bytes).
     2. Solana Base58 private keys (standalone 87-88 chars and assigned/prefixed 43-88 chars).
     3. EVM / hex private keys (0x-prefixed 64 chars and assigned/prefixed raw hex).
     4. BIP-39 seed phrases (12, 15, 18, 21, 24 words with case-insensitivity, backslash continuations, hyphen and comment boundary protection).
     5. API tokens (Anthropic, OpenAI, Google/Gemini, HuggingFace, GitHub PAT, AWS Key/Secret, Stripe, Slack, Solana RPC).
     6. `.env` sensitive key-value assignments.
     7. Generic sensitive credential assignments with arbitrary naming prefixes.
   - `engine.py`: Coordinates rule scanning, deduplication, reverse-index replacement, O(log N) line mapping via binary search, and `IngestResult` hunk updating.
3. **Repository Fixtures**:
   - `fixtures/secrets/`: Complete fixture set (`solana_keypair.json`, `solana_keys.ts`, `ethereum_wallet.rs`, `seed_phrases.txt`, `.env.example`, `secrets_staged.diff`) and `manifest.json`. **Recall is 100%**.
   - `fixtures/injections/`: Adversarial prompt injection attacks (`system_override_comment.diff`, `jailbreak_variable.diff`, `markdown_breakout.diff`, `delimiter_collision.diff`, `exfiltration_url.diff`) and `manifest.json`.
4. **CLI `--dry-run` Flow**:
   - `emc quiz --dry-run`: Ingests diff, redacts secrets locally, renders Rich summary table and detected secrets table with masked previews, flags adversarial prompt injection warnings if detected, and prints the exact sanitized and encapsulated diff payload without making any network call.
   - Supports `--staged`, `--commit <rev>`, and `--stdin`.
5. **Test Suite**:
   - 57 unit tests in `tests/test_cli.py`, `tests/test_doctor.py`, `tests/test_ingest.py`, `tests/test_redact.py`, `tests/test_injection.py`, and `tests/test_cli_dry_run.py`.

---

## Verification Commands
To verify Stage 1 independently, run from the `explain-my-own-code` directory:

```bash
# 1. Run unit test suite (57 passing tests)
pytest

# 2. Check code formatting and linting
ruff check .
ruff format --check .

# 3. Check static types
mypy src tests

# 4. Try dry-run with the secrets fixture diff
Get-Content fixtures/secrets/secrets_staged.diff | emc quiz --stdin --dry-run

# 5. Try dry-run on current repository changes
emc quiz --dry-run
```
