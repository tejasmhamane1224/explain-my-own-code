# Project Status: explain-my-own-code (`emc`)

## Current Stage
**Stage 0: Plan + Scaffold** — **COMPLETED**

---

## Stage Progress Checklist
- [x] **Stage 0: Plan + Scaffold**: Repo layout, `CLAUDE.md`, `PLAN.md` with competitor comparison, `DECISIONS.md`, `STATUS.md`, CI workflow, Typer/Rich CLI skeleton, `emc doctor` diagnostics, unit tests.
- [ ] **Stage 1: Ingest + Redact + Injection Fixtures**: Git diff ingestion (staged, commit range, stdin), hunk segmentation, secret redaction (Base58, hex, seed phrases, envs), `--dry-run`, prompt injection fixtures.
- [ ] **Stage 2: Detectors + Ranking (No LLM)**: Solana/Anchor rules (missing Signer, UncheckedAccount, unchecked math, PDA bump), TS wallet rules (lamports/decimals, base units, RPCs), generic rules, hunk ranking.
- [ ] **Stage 3: LLM Layer + Generation + Validator**: Provider abstraction (Anthropic, Fake, Local), disk cache, question schemas, 4-step quality validator.
- [ ] **Stage 4: Session + Grading**: Interactive terminal quiz loop (Rich), hint ladder, deterministic matchers, LLM rubric judge for free text.
- [ ] **Stage 5: Ledger + Mastery + Report/Review**: `.emc/ledger.jsonl`, Leitner box mastery tracking, `emc report`, `emc review`.
- [ ] **Stage 6: Modes, Gate, Hooks, CI-Safe Behavior**: `.emc.toml` configuration, `off` / `warn` / `gate` modes, pre-commit hook installer, Comprehension trailer, CI bypass.
- [ ] **Stage 7: Evaluation Suite (`emc eval`)**: 30+ seeded diffs (20 Anchor, 10 TS), ablation vs naive single-prompt baseline, `docs/EVAL.md`.
- [ ] **Stage 8: Documentation & Security Hardening**: Comprehensive README with honest competitor matrix, threat model, `SECURITY.md`, `CONTRIBUTING.md`.
- [ ] **Stage 9: Release Readiness**: Packaging dry-run (`pipx`), changelog, versioning, GitHub Actions CI matrix.

---

## Stage 0 Deliverables Summary
1. **Repository Layout**: Standalone repository structure with clean separation under `explain-my-own-code/`.
2. **Project Configuration**: `pyproject.toml` supporting Python >= 3.12, Typer, Rich, Pydantic, Ruff, Mypy, and Pytest.
3. **Core Documentation**:
   - `CLAUDE.md`: Operating rules, principles, pipeline architecture, quality gate requirements.
   - `PLAN.md`: Honest competitor matrix (`arivcode`, `bel-ai-jar`, `cognit`, Claude quiz skills), architecture diagram, quality gate, Leitner mastery, stage roadmap.
   - `DECISIONS.md`: ADRs for CLI choice, deterministic detectors, quality gate, injection defense, redaction, doctor architecture.
   - `STATUS.md`: Real-time stage tracking and verification records.
4. **CLI & Diagnostics**:
   - `emc --help`: Full Typer command tree with rich formatting.
   - `emc doctor`: Multi-point environment diagnostic suite checking Python runtime (>=3.12), git installation, repository context, Anthropic API key masking, model resolution, `.emc.toml` configuration, and `.emc/` state. Supports `--verbose` and `--json`.
   - `emc config`: Active configuration inspection.
   - `emc init`: Default `.emc.toml` initialization.
   - `emc hook`: Git hook installation and removal commands.
5. **CI Automation**: `.github/workflows/ci.yml` verifying linting (`ruff`), typing (`mypy`), testing (`pytest`), and CLI smoke runs on Ubuntu + Python 3.12.
6. **Test Suite**: Comprehensive unit tests in `tests/test_cli.py` and `tests/test_doctor.py`.

---

## Verification Commands
To verify Stage 0 independently, run from the `explain-my-own-code` directory:

```bash
# 1. Install in editable development mode
pip install -e ".[dev]"

# 2. Run unit tests
pytest

# 3. Check code formatting and linting
ruff check .
ruff format --check .

# 4. Check static types
mypy src

# 5. Test CLI commands
emc --help
emc doctor
emc doctor --json
emc config
```
