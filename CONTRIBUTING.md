# Contributing to explain-my-own-code (`emc`)

Thank you for your interest in contributing to `explain-my-own-code`! `emc` is an open-source, local-first developer safety CLI designed to stop engineers from rubber-stamping AI-generated code diffs.

We hold our codebase to rigorous engineering standards: **281 passing tests, zero linter warnings, 100% static type safety, and reproducible empirical benchmarks**.

---

## Code of Conduct & Core Principles

All contributors are expected to uphold our 5 core engineering tenets:
1. **GROUNDED**: Every question generated or tested must cite real lines from the diff. Never invent fake code or phantom line numbers.
2. **SAFE**: Diff content is untrusted input. Redact secrets locally before any network call. Protect against prompt injection.
3. **HONEST**: `emc` produces evidence of comprehension, not mathematical proof. No fabricated metrics or marketing exaggerations.
4. **MEASURABLE**: Any claim regarding detection recall, question grounding, or grader accuracy must be backed by reproducible benchmarks in `emc eval`.
5. **FINISHABLE**: Maintain clear, modular boundaries and prioritize production quality over speculative scope creep.

---

## Development Environment Setup

### Prerequisites
- **Python 3.11, 3.12, 3.13, or 3.14**
- **Git** (version 2.25+)
- Recommended: [Poetry](https://python-poetry.org/) or standard virtual environments (`venv`)

### 1. Clone Repository & Setup Virtual Environment
```bash
git clone https://github.com/tejasmhamane1224/explain-my-own-code.git
cd explain-my-own-code

# Create and activate virtual environment
python -m venv .venv

# On POSIX (Linux/macOS):
source .venv/bin/activate
# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1
```

### 2. Install Development Dependencies
```bash
# Install in editable mode with development dependencies
pip install -e ".[dev]"
```

### 3. Verify Local Setup
```bash
# Run the complete test suite (281 tests)
pytest

# Run linter and formatting checks
ruff check .
ruff format --check .

# Run static type checks
mypy src tests

# Verify system diagnostics
python -m emc.cli doctor
```

---

## Codebase Architecture

```
src/emc/
├── cli.py             # Typer CLI application entrypoint
├── concepts.yaml      # Canonical 16-concept security & precision taxonomy
├── ingest/            # Git diff ingestion, structured hunk parser, 1-indexed line mapper
├── redact/            # Local secret scanner (Solana base58, EVM hex, BIP-39, API keys)
├── detect/            # Deterministic static risk rules (Anchor Rust, TS wallet, generic smells)
│   ├── models.py      # Detection findings, severity weights, ranked hunks
│   ├── rust_anchor.py # 8 Anchor smart contract vulnerability detectors
│   ├── ts_wallet.py   # 4 TypeScript & Solana wallet precision detectors
│   ├── generic.py     # 4 Generic code smells (bypass flags, log leaks, fallbacks)
│   ├── ranking.py     # Multi-factor hunk risk ranking engine
│   └── taxonomy.py    # Taxonomy registry and concept validator
├── llm/               # LLM provider interface (Anthropic, Fake, Local), sha256 disk cache
├── questions/         # 5 question schemas, generator, and 4-step quality gate
├── session/           # Interactive terminal quiz loop (Rich), hint ladder, TTY display
├── grade/             # Deterministic matcher & calibrated rubric LLM judge with fallback
├── ledger/            # Leitner 5-box mastery state machine, OS-locked append-only ledger
├── gate/              # Commit gate verdicts (off, warn, gate) and git trailer injector
├── hooks/             # Git pre-commit & commit-msg hook manager with foreign hook protection
└── eval/              # 31-bug evaluation benchmark runner and baseline ablation study
```

---

## How to Add a New Deterministic Detector

Deterministic static detectors are the heart of `emc`—they ensure questions target real vulnerabilities without relying on LLM guesswork.

### Step 1: Register Concept in `concepts.yaml`
Add your concept definition to `concepts.yaml`:
```yaml
concepts:
  - id: anchor.your_new_rule
    name: "Anchor Your New Vulnerability Rule"
    category: anchor
    severity: HIGH
    description: "Detailed description of what makes this code dangerous."
    references:
      - "https://solana.com/docs/security/..."
```

### Step 2: Implement Detector Function
Create or update the detector in `src/emc/detect/rust_anchor.py` or `src/emc/detect/ts_wallet.py`:
```python
def detect_your_new_rule(diff: FileDiff) -> list[DetectionFinding]:
    findings: list[DetectionFinding] = []
    # Inspect hunks, lines, and AST/regex patterns
    # Append DetectionFinding with exact line numbers and concept_id
    return findings
```
Wire the new detector into `src/emc/detect/engine.py`.

### Step 3: Add Positive and Negative Diff Fixtures
Every detector rule **MUST** include both a positive and negative unified diff fixture in `fixtures/detectors/`:
- `fixtures/detectors/<rule_id>_positive.diff`: Contains the exact vulnerability; detector must find it.
- `fixtures/detectors/<rule_id>_negative.diff`: Contains the correct/safe pattern; detector must produce zero findings.

### Step 4: Register in `fixtures/detectors/manifest.json`
```json
{
  "rule_id": "anchor.your_new_rule",
  "concept": "anchor.your_new_rule",
  "positive_fixture": "anchor_your_new_rule_positive.diff",
  "negative_fixture": "anchor_your_new_rule_negative.diff",
  "expected_findings": 1
}
```

### Step 5: Verify True Positive & False Positive Rates
Run the automated detector test suite:
```bash
pytest tests/test_detectors.py -v
```
All positive fixtures must pass with 100% recall, and all negative fixtures must pass with 0 false positives.

---

## How to Add Evaluation Benchmark Diffs

To expand the evaluation suite (`docs/EVAL.md`):
1. Create a minimal, self-contained unified diff in `fixtures/eval/diffs/` or add a programmatic mutation operator in `src/emc/eval/mutation.py`.
2. Register the entry in `fixtures/eval/manifest.json` specifying:
   - `id`: Unique diff identifier.
   - `concept`: Corresponding taxonomy concept ID.
   - `difficulty`: `easy`, `medium`, or `hard`.
3. Run the evaluation benchmark to ensure it surfaces:
   ```bash
   python -m emc.cli eval --ablation --output docs/EVAL.md
   ```

---

## Pull Request Guidelines

1. **Atomic Commits**: Use clear, conventional commit messages:
   - `feat(detect): add anchor account close validation rule`
   - `fix(redact): prevent false positives on base58 public keys`
   - `docs(threat-model): clarify trust boundaries`
2. **Never Break the Gate**:
   - `pytest` must pass 100% (all 281+ tests).
   - `ruff check .` must report zero errors.
   - `mypy src tests` must report zero type errors.
3. **No Phantom Line Numbers or Untrusted Diffs**:
   - Any new question type or feature must respect the 4-step quality gate.
4. **Documentation**:
   - If adding a new CLI flag or configuration setting, update `README.md` and `.emc.toml`.

---

## Questions and Community

For questions, discussions, or architectural feedback, please open an issue on GitHub or reach out directly to the maintainers. Thank you for making AI-assisted engineering safer!
