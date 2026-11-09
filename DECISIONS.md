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
