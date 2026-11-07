# explain-my-own-code (`emc`)

> Checks whether a developer actually understands a code diff, especially AI-generated code.

## Overview
`emc` reads a diff, finds the hunks most likely to be misunderstood, asks grounded questions, grades the answers, and tracks which concepts the developer is weak at. Strongest on Solana/Anchor (Rust) and TypeScript wallet code, where one misunderstood line can lose funds.

## Principles
1. **GROUNDED**: Every question cites real lines from the diff. No invented code, ever.
2. **SAFE**: Diff content is untrusted input (prompt injection). Never execute analyzed code. Redact secrets before any network call.
3. **HONEST**: `emc` produces evidence of understanding, not proof. No fabricated metrics anywhere.
4. **MEASURABLE**: Each claim is backed by `emc eval`.
5. **FINISHABLE**: P0 scope first; everything else is optional.

## Quickstart
```bash
# Diagnostic check
emc doctor

# CLI help
emc --help
```
