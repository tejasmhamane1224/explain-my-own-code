"""Secret redaction engine, rules, and models."""

from emc.redact.engine import Redactor, redact_diff
from emc.redact.models import RedactionFinding, RedactionResult
from emc.redact.rules import (
    find_api_keys,
    find_bip39_seed_phrases,
    find_env_secrets,
    find_generic_secrets,
    find_hex_private_keys,
    find_solana_base58_keys,
    find_solana_keypair_arrays,
    mask_secret,
)

__all__ = [
    "RedactionFinding",
    "RedactionResult",
    "Redactor",
    "find_api_keys",
    "find_bip39_seed_phrases",
    "find_env_secrets",
    "find_generic_secrets",
    "find_hex_private_keys",
    "find_solana_base58_keys",
    "find_solana_keypair_arrays",
    "mask_secret",
    "redact_diff",
]
