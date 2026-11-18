<p align="center">
  <img src="web/hero-hands.jpg" alt="emc — Explain My Own Code" width="100%">
</p>

<h1 align="center">explain-my-own-code</h1>

<p align="center">
  <strong>Prove you understand your own diff — before it ships.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/explain-my-own-code/"><img src="https://img.shields.io/pypi/v/explain-my-own-code.svg?style=flat-square&color=blue" alt="PyPI version"></a>
  <a href="https://github.com/tejasmhamane1224/explain-my-own-code/actions"><img src="https://img.shields.io/badge/tests-282%20passing-brightgreen?style=flat-square" alt="282 tests passing"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/python-3.12%20%7C%203.13-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.12 | 3.13"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/badge/code%20style-ruff-000?style=flat-square" alt="Ruff"></a>
  <a href="http://mypy-lang.org"><img src="https://img.shields.io/badge/type%20checked-mypy-blue?style=flat-square" alt="Mypy"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="MIT License"></a>
  <a href="https://explain-my-own-code.vercel.app"><img src="https://img.shields.io/badge/live-explain--my--own--code.vercel.app-F32E35?style=flat-square" alt="Live Site"></a>
</p>

---

## What is `emc`?

A local-first Python CLI and git commit gate built for **Solana/Anchor Rust** and **TypeScript wallet** diffs. It scrubs secrets locally, surfaces 100% of seeded vulnerabilities with 16 deterministic detectors, and forces developers to prove comprehension through an interactive terminal quiz — before code ships.

No LLM guesswork for detection. No secrets leaving your machine. No rubber-stamping AI-generated PRs.

---

## 20-Second Install

```bash
pipx install explain-my-own-code
emc doctor        # verify install
emc init           # create .emc.toml
emc hook install   # wire up pre-commit gate
```

Then just commit normally:

```bash
git add -p
git commit -m "feat(vault): add user deposit instruction"
# → emc intercepts the diff, detects risks, quizzes you, gates the commit.
```

---

## Why `emc` Exists

AI coding tools generate syntactically convincing PRs in seconds. But:

- **The Optical Illusion of Correctness** — AI-generated code looks clean and well-commented, masking catastrophic logical oversights.
- **High-Stakes Vulnerabilities** — In Solana/Anchor smart contracts and TypeScript wallet logic, a single missing signer check or unit conversion mismatch leads to immediate exploit and drained reserves.
- **Naive Quiz Tools Fail** — They ask trivial trivia, hallucinate line numbers, leak answer keys, and transmit raw private keys to remote LLMs.

`emc` is the fix: a hardened, multi-layer verification pipeline that catches what humans glaze over.

---

## The 9-Stage Pipeline

```
                 [ Git Diff: Staged / Commit / Stdin ]
                                   │
                                   ▼
                   ┌──────────────────────────────┐
                   │    1. INGEST & LINE MAP      │  structured hunks, 1-indexed lines, .emcignore
                   └───────────────┬──────────────┘
                                   │
                                   ▼
                   ┌──────────────────────────────┐
                   │   2. LOCAL SECRET REDACTOR   │  BIP-39, Solana base58, EVM hex, API keys
                   └───────────────┬──────────────┘
                                   │
                                   ▼
                   ┌──────────────────────────────┐
                   │ 3. DETERMINISTIC DETECTORS   │  16 rules: Anchor Rust, TS Wallet, Smells
                   └───────────────┬──────────────┘
                                   │
                                   ▼
                   ┌──────────────────────────────┐
                   │    4. RISK RANK & PLAN       │  multi-factor severity & file multipliers
                   └───────────────┬──────────────┘
                                   │
                                   ▼
                   ┌──────────────────────────────┐
                   │ 5. LLM GENERATION & CACHE    │  JSON schema, sha256 disk cache, token budget
                   └───────────────┬──────────────┘
                                   │
                                   ▼
                   ┌──────────────────────────────┐
                   │   6. 4-STEP QUALITY GATE     │  grounding, no leaks, solvability, ambiguity
                   └───────────────┬──────────────┘
                                   │
                                   ▼
                   ┌──────────────────────────────┐
                   │   7. INTERACTIVE TERMINAL    │  Rich TTY UI, syntax highlighting, hint ladder
                   └───────────────┬──────────────┘
                                   │
                                   ▼
                   ┌──────────────────────────────┐
                   │  8. HYBRID GRADING ENGINE    │  deterministic matcher + rubric LLM judge
                   └───────────────┬──────────────┘
                                   │
         ┌─────────────────────────┴─────────────────────────┐
         ▼                                                   ▼
┌─────────────────────────────────┐         ┌─────────────────────────────────┐
│ 9a. LEITNER 5-BOX MASTERY      │         │ 9b. COMMIT GATE & TRAILER       │
│ Append-only .emc/ledger.jsonl  │         │ Modes: off / warn / gate        │
│ Concept spaced repetition      │         │ Comprehension: 4/5 trailer      │
│ Targeted 'emc review' replay   │         │ Non-interactive CI bypass       │
└─────────────────────────────────┘         └─────────────────────────────────┘
```

---

## Benchmark Results

Evaluated against 31 seeded vulnerabilities (21 Anchor Rust, 10 TypeScript), 17 secret fixtures, 5 prompt injection attacks, and 30 hand-labeled developer explanations. Full methodology: [docs/EVAL.md](docs/EVAL.md).

| Metric | Naive Baseline | **emc** | Δ |
|:---|:---:|:---:|:---:|
| Bug Surfacing Rate | 12.9% | **100.0%** | +87.1% |
| Grounded Questions | 0.0% | **100.0%** | +100.0% |
| Secret Redaction Recall | 0.0% (17 leaked) | **100.0%** (0 leaked) | −17 leaks |
| Injection Resistance | 0.0% (5 exploited) | **100.0%** (0 exploited) | −5 exploits |
| Grader Agreement | 60.0% | **96.7%** | +36.7% |
| Grader Recall (Bad Answers) | 66.7% | **100.0%** | +33.3% |
| Cost per Session | $0.012 | **$0.002** | −85% |
| Pipeline Latency | 2,400 ms | **48 ms** | 65× faster |

---

## 16 Deterministic Detectors

No LLM. No hallucination. Pure static analysis on changed hunks.

### Anchor Rust Smart Contracts (8 rules)

| Rule | What it catches |
|:---|:---|
| `anchor.missing_signer` | Privileged accounts missing `Signer<'info>` or `has_one` |
| `anchor.unchecked_account` | `UncheckedAccount` without `/// CHECK:` safety docs |
| `math.unchecked_arith` | Raw `+` `-` `*` on balances instead of `checked_*` / `saturating_*` |
| `anchor.pda_seeds` | PDA seeds missing bump verification or hardcoded bumps |
| `anchor.invoke_signed` | `invoke_signed` with invalid or empty signer seeds |
| `anchor.realloc_close` | Realloc missing payer/zero init, manual lamport clearing |
| `anchor.remaining_accounts` | Iteration over dynamic accounts without ownership checks |
| `anchor.unverified_cpi` | CPI program accounts typed as untyped `AccountInfo` |

### TypeScript & Solana Wallet (4 rules)

| Rule | What it catches |
|:---|:---|
| `ts.lamport_units` | Mixing SOL and lamport units (10⁹) or float math on balances |
| `ts.base_units` | Unscaled decimal amounts in token transfer/mint instructions |
| `ts.address_validation` | Unhandled `new PublicKey()` without try/catch or curve validation |
| `ts.hardcoded_rpc` | Hardcoded mainnet/sensitive RPC endpoints |

### Generic Code Smells (4 rules)

| Rule | What it catches |
|:---|:---|
| `generic.bypass_flag` | `skip_auth`, `no_verify`, `@ts-ignore`, `dangerouslySetInnerHTML` |
| `generic.sensitive_log` | Logging credentials, private keys, or tokens |
| `generic.hardcoded_fallback` | Insecure defaults like `process.env.SECRET \|\| "default"` |
| `generic.empty_catch` | Silent exception swallowing |

---

## CLI Reference

```
emc init     [--mode warn]                    Create .emc.toml in repo root
emc doctor                                    Pre-flight health checks
emc detect   [--staged | --json]              Run detectors, output ranked risk hunks
emc quiz     [--staged | --commit <rev>]      Interactive comprehension session
emc generate [--provider anthropic | fake]    Generate question models for a diff
emc report   [--weak-only | --json]           Leitner mastery dashboard
emc review   [--limit 5 | --concept <id>]     Targeted replay of weak concepts
emc hook     install [--force]                Install git pre-commit/commit-msg hooks
emc eval     [--ablation | --output <path>]   Run 31-bug evaluation benchmark
emc config                                    Print effective .emc.toml settings
```

---

## Configuration

```toml
# .emc.toml
[core]
mode = "warn"           # off | warn | gate
threshold = 70          # minimum passing score (0-100)
skip_allowed = true     # allow 'S' to skip during quiz

[git]
commit_trailer = true   # append comprehension score to commit msg
trailer_style = "fraction"  # fraction | percentage | detailed

[llm]
provider = "anthropic"
model = "claude-3-7-sonnet-latest"
max_cost_usd = 0.05
```

---

## Security & Privacy

- **Local-First**: Parsing, indexing, redaction, and detection run entirely on your machine.
- **Zero Telemetry**: No crash reporters, analytics, or remote beacons.
- **Secret Redaction**: Diffs scrubbed before any payload reaches an LLM provider.
- **CI-Safe**: Non-TTY / `CI=true` environments exit cleanly without stalling pipelines.

See [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) for the STRIDE threat model and [SECURITY.md](SECURITY.md) for the vulnerability disclosure policy.

---

## Competitor Matrix

| Capability | arivcode | bel-ai-jar | cognit | AI Chat | **emc** |
|:---|:---:|:---:|:---:|:---:|:---:|
| Domain Detectors | None | AST (Python) | None | None | **16 rules** |
| Snippet Grounding | Loose | Out-of-context | LLM summary | Hallucinates | **100% exact** |
| Secret Redaction | Regex | None | None | Dependent on LLM | **100% recall** |
| Injection Defense | Fragile | Unchecked | None | Vulnerable | **Data isolation** |
| Quality Gate | None | JSON parse | None | None | **4-step gate** |
| Question Types | MC only | MC + T/F | Flashcards | Chat | **5 types** |
| Grading | Exact string | Exact string | Subjective | Chat agreement | **Hybrid rubric** |
| Mastery Tracking | Global score | Session | Basic SRS | None | **Leitner 5-box** |
| Git Integration | Script | Alias | Web app | Copy-paste | **Native hooks** |
| Eval Suite | Anecdotal | None | None | None | **31-bug benchmark** |

---

## Project Structure

```
src/emc/
├── ingest/       # Diff parsing, hunk splitting, line mapping
├── redact/       # Local secret redaction engine
├── detect/       # 16 deterministic static detectors
├── plan/         # Risk ranking and question strategy
├── llm/          # LLM generation with SHA-256 disk cache
├── questions/    # 4-step quality gate validation
├── session/      # Interactive terminal quiz (Rich)
├── grade/        # Hybrid deterministic + rubric grading
├── gate/         # Commit gate modes (off/warn/gate)
├── ledger/       # Leitner 5-box spaced repetition storage
├── hooks/        # Git hook installation and management
├── eval/         # Automated benchmark and ablation suite
├── cli.py        # Typer CLI entrypoint
├── config.py     # .emc.toml configuration loader
├── doctor.py     # Pre-flight system diagnostics
└── concepts.yaml # Rule definitions for all 16 detectors
```

---

## Development

```bash
git clone https://github.com/tejasmhamane1224/explain-my-own-code.git
cd explain-my-own-code
python -m venv .venv && .venv/Scripts/activate    # or source .venv/bin/activate
pip install -e ".[dev]"
pytest                # 282 tests
ruff check .          # lint
ruff format --check . # format check
mypy src tests        # type check
```

---

## Contributing

Contributions welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for environment setup, adding detector rules, fixture requirements, and PR guidelines.

---

## Links

| | |
|:---|:---|
| **Live Site** | [explain-my-own-code.vercel.app](https://explain-my-own-code.vercel.app) |
| **Release v1.0.0** | [GitHub Release](https://github.com/tejasmhamane1224/explain-my-own-code/releases/tag/v1.0.0) |
| **Eval Report** | [docs/EVAL.md](docs/EVAL.md) |
| **Threat Model** | [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) |
| **Changelog** | [CHANGELOG.md](CHANGELOG.md) |
| **CI** | [GitHub Actions](https://github.com/tejasmhamane1224/explain-my-own-code/actions) |

---

<p align="center">
  MIT © <a href="https://github.com/tejasmhamane1224">Tejas Mhamane</a>
</p>
