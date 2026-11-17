# Security Policy: explain-my-own-code (`emc`)

The maintainers of `explain-my-own-code` take security and privacy seriously. Because `emc` operates on developers' proprietary source code diffs, sensitive git repositories, and cryptographic logic, we maintain strict architectural security standards.

---

## Supported Versions

Security updates are actively applied to the following release tracks:

| Version | Supported | Security Maintenance |
| :--- | :---: | :--- |
| `1.0.x` | :white_check_mark: | Active full support and security patches |
| `0.1.x` | :white_check_mark: | Critical security patches only |
| `< 0.1.0` | :x: | End of life; please upgrade to latest release |

---

## Core Security Architecture & Guarantees

1. **Local-First Processing**: Diff ingestion, hunk splitting, 1-indexed line mapping, deterministic risk detection, and ledger management execute entirely on your local machine.
2. **Zero Telemetry**: `emc` contains **zero telemetry**, analytics beacons, crash collectors, or background tracking.
3. **Pre-Transmission Secret Redaction**: Before any diff payload is transmitted to an external LLM provider, all private keys (Solana Base58, EVM hex, Solana keypair arrays), BIP-39 mnemonic seed phrases, API credentials, and `.env` values are redacted locally with cryptographic masks.
4. **No Code Execution**: `emc` inspects static diffs. It never compiles, interprets, or executes analyzed code.
5. **Prompt Injection Hardening**: All diffs are treated as untrusted external data and quarantined from LLM system instructions.

For a detailed analysis of our trust boundaries and STRIDE mitigations, consult the [Threat Model](docs/THREAT_MODEL.md).

---

## Reporting a Security Vulnerability

If you discover a security vulnerability, private key bypass, prompt injection exploit, or secret redaction failure in `emc`, **please do not disclose it publicly via GitHub Issues or pull requests.**

### How to Report Privately

Please report security issues via one of the following private channels:

- **GitHub Private Vulnerability Reporting**: Submit a private advisory via [GitHub Security Advisories](https://github.com/tejasmhamane1224/explain-my-own-code/security/advisories/new) (preferred).
- **Direct Email**: Send encrypted details to `tejas@mhamane.dev` with the subject tag `[SECURITY: EMC]`.

### What to Include in Your Report

To help us triage and resolve the issue quickly, please provide:
1. A clear description of the vulnerability and its potential security impact.
2. Step-by-step reproduction instructions or a minimal reproducible unified diff.
3. The specific version of `emc` and Python runtime environment (`emc doctor` output).
4. Any proposed fixes or proof-of-concept diffs.

---

## Response & Disclosure SLA

We adhere to a coordinated vulnerability disclosure policy:

| Phase | Target Timeline | Action |
| :--- | :--- | :--- |
| **Initial Acknowledgment** | **< 24 hours** | Confirmation of report receipt and initial assessment. |
| **Triage & Reproduction** | **< 72 hours** | Validation of severity, root-cause identification, and assignment. |
| **Patch & Fix Verification** | **< 7 days** | Delivery of candidate patch and private verification with reporter. |
| **Public Release & Advisory** | Coordinated | Release of patched version on PyPI and publication of CVE/Advisory. |

Credit will be gladly given to security researchers who report vulnerabilities following responsible disclosure practices.
