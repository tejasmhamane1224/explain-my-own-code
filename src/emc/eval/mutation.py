"""Mutation generator for injecting realistic Solana/Anchor and TypeScript vulnerabilities."""

from __future__ import annotations

import difflib
import re
from typing import Callable

from pydantic import BaseModel, Field


class MutationResult(BaseModel):
    """Result of a code mutation operation."""

    mutation_id: str
    concept_id: str
    rule_id: str
    description: str
    file_path: str
    original_code: str
    mutated_code: str
    diff: str
    line_number: int = Field(default=1, ge=1)


def create_git_diff(file_path: str, original: str, mutated: str) -> str:
    """Generate a standard git unified diff between original and mutated code."""
    orig_lines = original.splitlines(keepends=True)
    mut_lines = mutated.splitlines(keepends=True)

    norm_path = file_path.replace("\\", "/").lstrip("/")
    diff_lines = list(
        difflib.unified_diff(
            orig_lines,
            mut_lines,
            fromfile=f"a/{norm_path}",
            tofile=f"b/{norm_path}",
            lineterm="",
        )
    )

    if not diff_lines:
        return ""

    git_header = f"diff --git a/{norm_path} b/{norm_path}\n"
    diff_body = "\n".join(diff_lines)
    return git_header + diff_body + "\n"


# --- Anchor (Rust) Mutators ---


def mutate_anchor_missing_signer(
    code: str, file_path: str = "programs/vault/src/lib.rs"
) -> MutationResult:
    """Mutate Signer<'info> to AccountInfo<'info> in Anchor account struct."""
    pattern = r"pub\s+(authority|admin|owner|payer|user)\s*:\s*Signer<'info>"
    match = re.search(pattern, code)
    if not match:
        # Fallback to replacing #[account(signer)]
        if "#[account(signer)]" in code:
            mutated = code.replace("#[account(signer)]\n", "")
            field_name = "authority"
        else:
            raise ValueError(f"Could not find Signer<'info> or #[account(signer)] in code:\n{code}")
    else:
        field_name = match.group(1)
        mutated = re.sub(
            pattern,
            f"pub {field_name}: AccountInfo<'info>",
            code,
            count=1,
        )

    # Calculate line number where mutation occurred
    lines = code.splitlines()
    line_no = 1
    for idx, line in enumerate(lines, start=1):
        if field_name in line:
            line_no = idx
            break

    diff = create_git_diff(file_path, code, mutated)
    return MutationResult(
        mutation_id="mut_anchor_missing_signer",
        concept_id="anchor.signer_check",
        rule_id="anchor.missing_signer",
        description="Removed Signer constraint on privileged authority account",
        file_path=file_path,
        original_code=code,
        mutated_code=mutated,
        diff=diff,
        line_number=line_no,
    )


def mutate_anchor_unchecked_account(
    code: str, file_path: str = "programs/vault/src/lib.rs"
) -> MutationResult:
    """Remove /// CHECK: safety doc comment above UncheckedAccount."""
    pattern = r"///\s*CHECK:[^\n]*\n"
    if not re.search(pattern, code):
        raise ValueError(f"Could not find '/// CHECK:' safety comment in code:\n{code}")

    mutated = re.sub(pattern, "", code, count=1)
    lines = code.splitlines()
    line_no = 1
    for idx, line in enumerate(lines, start=1):
        if "UncheckedAccount" in line:
            line_no = idx
            break

    diff = create_git_diff(file_path, code, mutated)
    return MutationResult(
        mutation_id="mut_anchor_unchecked_account",
        concept_id="anchor.account_types",
        rule_id="anchor.unchecked_account",
        description="Removed '/// CHECK:' safety documentation above UncheckedAccount",
        file_path=file_path,
        original_code=code,
        mutated_code=mutated,
        diff=diff,
        line_number=line_no,
    )


def mutate_math_unchecked_arith(
    code: str, file_path: str = "programs/vault/src/lib.rs"
) -> MutationResult:
    """Replace checked/saturating arithmetic with raw arithmetic operator."""
    sub_pattern = r"(\w+\.balance)\.checked_sub\((\w+)\)\.ok_or\([^)]+\)\?"
    add_pattern = r"(\w+\.balance)\.checked_add\((\w+)\)\.ok_or\([^)]+\)\?"

    if re.search(sub_pattern, code):
        mutated = re.sub(sub_pattern, r"\1 - \2", code, count=1)
    elif re.search(add_pattern, code):
        mutated = re.sub(add_pattern, r"\1 + \2", code, count=1)
    elif ".checked_sub(" in code:
        mutated = re.sub(r"\.checked_sub\(([^)]+)\)\.unwrap\(\)", r" - \1", code, count=1)
    elif ".checked_add(" in code:
        mutated = re.sub(r"\.checked_add\(([^)]+)\)\.unwrap\(\)", r" + \1", code, count=1)
    else:
        raise ValueError(f"Could not find checked arithmetic pattern in code:\n{code}")

    lines = code.splitlines()
    line_no = 1
    for idx, line in enumerate(lines, start=1):
        if "checked_" in line:
            line_no = idx
            break

    diff = create_git_diff(file_path, code, mutated)
    return MutationResult(
        mutation_id="mut_math_unchecked_arith",
        concept_id="math.checked_arith",
        rule_id="math.unchecked_arith",
        description="Replaced checked arithmetic with raw arithmetic operator",
        file_path=file_path,
        original_code=code,
        mutated_code=mutated,
        diff=diff,
        line_number=line_no,
    )


def mutate_anchor_pda_seeds(
    code: str, file_path: str = "programs/vault/src/lib.rs"
) -> MutationResult:
    """Remove bump validation or replace with hardcoded bump in PDA seeds constraint."""
    if "bump = account.bump" in code:
        mutated = code.replace("bump = account.bump", "bump = 254", 1)
    elif "bump = vault.bump" in code:
        mutated = code.replace("bump = vault.bump", "bump = 254", 1)
    elif ", bump" in code:
        mutated = code.replace(", bump", "", 1)
    elif "bump," in code:
        mutated = code.replace("bump,", "", 1)
    else:
        raise ValueError(f"Could not find bump validation in code:\n{code}")

    lines = code.splitlines()
    line_no = 1
    for idx, line in enumerate(lines, start=1):
        if "seeds" in line or "bump" in line:
            line_no = idx
            break

    diff = create_git_diff(file_path, code, mutated)
    return MutationResult(
        mutation_id="mut_anchor_pda_seeds",
        concept_id="anchor.pda_seeds",
        rule_id="anchor.pda_seeds",
        description="Removed canonical bump validation from PDA seeds constraint",
        file_path=file_path,
        original_code=code,
        mutated_code=mutated,
        diff=diff,
        line_number=line_no,
    )


def mutate_anchor_invoke_signed(
    code: str, file_path: str = "programs/vault/src/lib.rs"
) -> MutationResult:
    """Remove bump seed slice or empty seed slice from invoke_signed CPI call."""
    if "invoke_signed(" in code:
        mutated = re.sub(
            r"invoke_signed\s*\([^;]+\);?",
            "invoke_signed(&ix, &accounts, &[])?;",
            code,
            count=1,
        )
    else:
        raise ValueError(f"Could not find invoke_signed in code:\n{code}")

    lines = code.splitlines()
    line_no = 1
    for idx, line in enumerate(lines, start=1):
        if "invoke_signed" in line:
            line_no = idx
            break

    diff = create_git_diff(file_path, code, mutated)
    return MutationResult(
        mutation_id="mut_anchor_invoke_signed",
        concept_id="anchor.invoke_signed",
        rule_id="anchor.invoke_signed",
        description="Removed bump seed from invoke_signed PDA signer seed slice",
        file_path=file_path,
        original_code=code,
        mutated_code=mutated,
        diff=diff,
        line_number=line_no,
    )


def mutate_anchor_realloc_close(
    code: str, file_path: str = "programs/vault/src/lib.rs"
) -> MutationResult:
    """Remove realloc::payer and realloc::zero from account constraint."""
    if "realloc = 500" in code:
        mutated = code.replace(
            "realloc = 500, realloc::payer = payer, realloc::zero = true",
            "realloc = 500",
            1,
        )
    elif "realloc::payer" in code:
        mutated = re.sub(r",?\s*realloc::payer\s*=\s*\w+", "", code, count=1)
    elif "realloc::zero" in code:
        mutated = re.sub(r",?\s*realloc::zero\s*=\s*\w+", "", code, count=1)
    else:
        raise ValueError(f"Could not find realloc parameters in code:\n{code}")

    lines = code.splitlines()
    line_no = 1
    for idx, line in enumerate(lines, start=1):
        if "realloc" in line:
            line_no = idx
            break

    diff = create_git_diff(file_path, code, mutated)
    return MutationResult(
        mutation_id="mut_anchor_realloc_close",
        concept_id="anchor.realloc_close",
        rule_id="anchor.realloc_close",
        description="Removed mandatory realloc safety constraint (payer/zero)",
        file_path=file_path,
        original_code=code,
        mutated_code=mutated,
        diff=diff,
        line_number=line_no,
    )


def mutate_anchor_unverified_cpi(
    code: str, file_path: str = "programs/vault/src/lib.rs"
) -> MutationResult:
    """Replace Program<'info, Token> with untyped AccountInfo<'info>."""
    pattern = r"pub\s+(token_program|system_program)\s*:\s*Program<'info,\s*\w+>"
    match = re.search(pattern, code)
    if not match:
        raise ValueError(f"Could not find Program<'info, ...> in code:\n{code}")

    field_name = match.group(1)
    mutated = re.sub(
        pattern,
        f"pub {field_name}: AccountInfo<'info>",
        code,
        count=1,
    )

    lines = code.splitlines()
    line_no = 1
    for idx, line in enumerate(lines, start=1):
        if field_name in line:
            line_no = idx
            break

    diff = create_git_diff(file_path, code, mutated)
    return MutationResult(
        mutation_id="mut_anchor_unverified_cpi",
        concept_id="anchor.cpi_checks",
        rule_id="anchor.unverified_cpi",
        description="Replaced verified Program CPI account with untyped AccountInfo",
        file_path=file_path,
        original_code=code,
        mutated_code=mutated,
        diff=diff,
        line_number=line_no,
    )


# --- TypeScript / Wallet Mutators ---


def mutate_ts_base_units(code: str, file_path: str = "src/wallet/transfer.ts") -> MutationResult:
    """Omit decimal scaling in token transfer instruction call."""
    pattern = r"amount\s*\*\s*10\s*\*\*\s*decimals"
    if re.search(pattern, code):
        mutated = re.sub(pattern, "amount", code, count=1)
    elif "* 10 ** decimals" in code:
        mutated = code.replace(" * 10 ** decimals", "", 1)
    elif "BigInt(Math.floor(amount * (10 ** decimals)))" in code:
        mutated = code.replace("BigInt(Math.floor(amount * (10 ** decimals)))", "BigInt(amount)", 1)
    else:
        raise ValueError(f"Could not find decimal scaling in code:\n{code}")

    lines = code.splitlines()
    line_no = 1
    for idx, line in enumerate(lines, start=1):
        if "createTransferInstruction" in line or "amount" in line:
            line_no = idx
            break

    diff = create_git_diff(file_path, code, mutated)
    return MutationResult(
        mutation_id="mut_ts_base_units",
        concept_id="ts.base_units",
        rule_id="ts.base_units",
        description="Omitted token decimal exponent scaling in transfer instruction",
        file_path=file_path,
        original_code=code,
        mutated_code=mutated,
        diff=diff,
        line_number=line_no,
    )


def mutate_ts_lamport_units(code: str, file_path: str = "src/wallet/balance.ts") -> MutationResult:
    """Mix SOL UI units with lamports or perform float division on lamports."""
    if "fee * LAMPORTS_PER_SOL" in code:
        mutated = code.replace("Math.floor(balance - (fee * LAMPORTS_PER_SOL))", "balance - 0.5", 1)
    elif "solAmount * LAMPORTS_PER_SOL" in code:
        mutated = code.replace("solAmount * LAMPORTS_PER_SOL", "solAmount", 1)
    elif "balanceLamports + (solAmount * LAMPORTS_PER_SOL)" in code:
        mutated = code.replace(
            "balanceLamports + (solAmount * LAMPORTS_PER_SOL)",
            "balanceLamports + solAmount",
            1,
        )
    elif "const half = lamports / 2n;" in code:
        mutated = code.replace("const half = lamports / 2n;", "const half = lamports / 2.0;", 1)
    else:
        raise ValueError(f"Could not find lamport scaling pattern in code:\n{code}")

    lines = code.splitlines()
    line_no = 1
    for idx, line in enumerate(lines, start=1):
        if "remainingLamports" in line or "lamports" in line or "balance" in line:
            line_no = idx
            break

    diff = create_git_diff(file_path, code, mutated)
    return MutationResult(
        mutation_id="mut_ts_lamport_units",
        concept_id="ts.lamport_units",
        rule_id="ts.lamport_units",
        description="Mixed SOL UI float amount with raw integer lamports",
        file_path=file_path,
        original_code=code,
        mutated_code=mutated,
        diff=diff,
        line_number=line_no,
    )


def mutate_ts_address_validation(
    code: str, file_path: str = "src/wallet/address.ts"
) -> MutationResult:
    """Remove try/catch around new PublicKey(userInput) or substitute naive length check."""
    if "PublicKey.isOnCurve(" in code:
        mutated = re.sub(r"PublicKey\.isOnCurve\([^)]+\)", "recipient.length === 44", code, count=1)
    elif "try {" in code:
        pattern = (
            r"\s*try\s*\{\s*const\s+pubkey\s*=\s*new\s+PublicKey\(([^)]+)\);\s*"
            r"return\s+connection\.getAccountInfo\(pubkey\);\s*\}\s*catch[^{]*\{[^}]*\}"
        )
        replacement = (
            r"\n    const pubkey = new PublicKey(\1);\n"
            r"    return connection.getAccountInfo(pubkey);"
        )
        mutated = re.sub(pattern, replacement, code, count=1)
    elif "PublicKey(" in code:
        mutated = code.replace("validatePubkey(input)", "new PublicKey(input)", 1)
    else:
        raise ValueError(f"Could not find PublicKey try/catch or curve validation in code:\n{code}")

    lines = code.splitlines()
    line_no = 1
    for idx, line in enumerate(lines, start=1):
        if "PublicKey" in line or "recipient" in line:
            line_no = idx
            break

    diff = create_git_diff(file_path, code, mutated)
    return MutationResult(
        mutation_id="mut_ts_address_validation",
        concept_id="ts.address_validation",
        rule_id="ts.address_validation",
        description="Removed try/catch address validation around new PublicKey constructor",
        file_path=file_path,
        original_code=code,
        mutated_code=mutated,
        diff=diff,
        line_number=line_no,
    )


def mutate_ts_hardcoded_rpc(code: str, file_path: str = "src/services/rpc.ts") -> MutationResult:
    """Inject hardcoded production mainnet RPC URL into connection constructor."""
    pattern = (
        r"const\s+endpoint\s*=\s*process\.env\.SOLANA_RPC_URL\s*\|\|\s*clusterApiUrl\([^)]+\);"
    )
    replacement = 'const endpoint = "https://api.mainnet-beta.solana.com";'

    if re.search(pattern, code):
        mutated = re.sub(pattern, replacement, code, count=1)
    elif "process.env.SOLANA_RPC_URL" in code:
        mutated = code.replace(
            "process.env.SOLANA_RPC_URL", '"https://api.mainnet-beta.solana.com"', 1
        )
    else:
        raise ValueError(f"Could not find dynamic RPC endpoint in code:\n{code}")

    lines = code.splitlines()
    line_no = 1
    for idx, line in enumerate(lines, start=1):
        if "endpoint" in line or "RPC" in line:
            line_no = idx
            break

    diff = create_git_diff(file_path, code, mutated)
    return MutationResult(
        mutation_id="mut_ts_hardcoded_rpc",
        concept_id="ts.rpc_security",
        rule_id="ts.hardcoded_rpc",
        description="Replaced dynamic RPC endpoint with hardcoded production mainnet URL",
        file_path=file_path,
        original_code=code,
        mutated_code=mutated,
        diff=diff,
        line_number=line_no,
    )


# --- Benign Seed Snippet Catalog ---

BENIGN_ANCHOR_SNIPPETS = {
    "vault_signer": (
        "#[derive(Accounts)]\n"
        "pub struct WithdrawVault<'info> {\n"
        "    #[account(mut)]\n"
        "    pub vault: Account<'info, Vault>,\n"
        "    pub authority: Signer<'info>,\n"
        "}\n"
    ),
    "oracle_checked": (
        "#[derive(Accounts)]\n"
        "pub struct ReadPrice<'info> {\n"
        "    /// CHECK: Oracle price feed is validated in instruction via Pyth SDK\n"
        "    pub oracle_feed: UncheckedAccount<'info>,\n"
        "    pub user: Signer<'info>,\n"
        "}\n"
    ),
    "vault_arithmetic": (
        "pub fn withdraw(ctx: Context<Withdraw>, amount: u64) -> Result<()> {\n"
        "    let vault = &mut ctx.accounts.vault;\n"
        "    vault.balance = vault.balance.checked_sub(amount).ok_or(ErrorCode::Over)?;\n"
        "    Ok(())\n"
        "}\n"
    ),
    "escrow_bump": (
        "#[derive(Accounts)]\n"
        "pub struct InitializeEscrow<'info> {\n"
        '    #[account(init, payer = authority, seeds = [b"escrow"], bump = account.bump)]\n'
        "    pub escrow: Account<'info, Escrow>,\n"
        "    #[account(mut)]\n"
        "    pub authority: Signer<'info>,\n"
        "}\n"
    ),
    "cpi_signed": (
        "pub fn transfer_pda(ctx: Context<TransferPda>) -> Result<()> {\n"
        '    invoke_signed(&ix, &accounts, &[&[b"vault", authority.as_ref(), &[vault.bump]]])?;\n'
        "    Ok(())\n"
        "}\n"
    ),
    "cpi_typed_program": (
        "#[derive(Accounts)]\n"
        "pub struct SplTransfer<'info> {\n"
        "    #[account(mut)]\n"
        "    pub source: Account<'info, TokenAccount>,\n"
        "    pub authority: Signer<'info>,\n"
        "    pub token_program: Program<'info, Token>,\n"
        "}\n"
    ),
    "realloc_safe": (
        "#[derive(Accounts)]\n"
        "pub struct ResizeRecord<'info> {\n"
        "    #[account(mut, realloc = 500, realloc::payer = payer, realloc::zero = true)]\n"
        "    pub record: Account<'info, Record>,\n"
        "    #[account(mut)]\n"
        "    pub payer: Signer<'info>,\n"
        "}\n"
    ),
}

BENIGN_TS_SNIPPETS = {
    "transfer_scaled": (
        "export function buildTransfer(\n"
        "    from: PublicKey, to: PublicKey, auth: PublicKey, amount: number, decimals: number\n"
        ") {\n"
        "    return createTransferInstruction(from, to, auth, amount * 10 ** decimals);\n"
        "}\n"
    ),
    "balance_scaled": (
        "export function deductFee(balance: number, fee: number): number {\n"
        "    const remainingLamports = Math.floor(balance - (fee * LAMPORTS_PER_SOL));\n"
        "    return remainingLamports;\n"
        "}\n"
    ),
    "address_safe": (
        "export function validateAddress(addressStr: string): boolean {\n"
        "    return PublicKey.isOnCurve(addressStr);\n"
        "}\n"
    ),
    "rpc_config": (
        "export function getSolanaConnection(): Connection {\n"
        "    const endpoint = process.env.SOLANA_RPC_URL || clusterApiUrl('devnet');\n"
        "    return new Connection(endpoint, 'confirmed');\n"
        "}\n"
    ),
}


class MutationGenerator:
    """Orchestrates mutation of benign Anchor and TypeScript code."""

    _MUTATOR_REGISTRY: dict[str, Callable[[str, str], MutationResult]] = {
        "anchor.missing_signer": mutate_anchor_missing_signer,
        "anchor.unchecked_account": mutate_anchor_unchecked_account,
        "math.unchecked_arith": mutate_math_unchecked_arith,
        "anchor.pda_seeds": mutate_anchor_pda_seeds,
        "anchor.invoke_signed": mutate_anchor_invoke_signed,
        "anchor.realloc_close": mutate_anchor_realloc_close,
        "anchor.unverified_cpi": mutate_anchor_unverified_cpi,
        "ts.base_units": mutate_ts_base_units,
        "ts.lamport_units": mutate_ts_lamport_units,
        "ts.address_validation": mutate_ts_address_validation,
        "ts.hardcoded_rpc": mutate_ts_hardcoded_rpc,
    }

    def available_mutations(self) -> list[str]:
        """List registered mutation rule keys."""
        return list(self._MUTATOR_REGISTRY.keys())

    def mutate(
        self,
        code: str,
        mutation_key: str,
        file_path: str = "programs/vault/src/lib.rs",
    ) -> MutationResult:
        """Apply a registered mutator to a code snippet."""
        if mutation_key not in self._MUTATOR_REGISTRY:
            raise KeyError(
                f"Unknown mutation key '{mutation_key}'. Available: {self.available_mutations()}"
            )
        mutator = self._MUTATOR_REGISTRY[mutation_key]
        return mutator(code, file_path)

    def generate_all_mutations(self) -> list[MutationResult]:
        """Generate mutations across the catalog of benign snippets."""
        results: list[MutationResult] = []

        # Anchor mutations
        results.append(
            self.mutate(
                BENIGN_ANCHOR_SNIPPETS["vault_signer"],
                "anchor.missing_signer",
                "programs/vault/src/lib.rs",
            )
        )
        results.append(
            self.mutate(
                BENIGN_ANCHOR_SNIPPETS["oracle_checked"],
                "anchor.unchecked_account",
                "programs/oracle/src/lib.rs",
            )
        )
        results.append(
            self.mutate(
                BENIGN_ANCHOR_SNIPPETS["vault_arithmetic"],
                "math.unchecked_arith",
                "programs/vault/src/lib.rs",
            )
        )
        results.append(
            self.mutate(
                BENIGN_ANCHOR_SNIPPETS["escrow_bump"],
                "anchor.pda_seeds",
                "programs/escrow/src/lib.rs",
            )
        )
        results.append(
            self.mutate(
                BENIGN_ANCHOR_SNIPPETS["cpi_signed"],
                "anchor.invoke_signed",
                "programs/vault/src/lib.rs",
            )
        )
        results.append(
            self.mutate(
                BENIGN_ANCHOR_SNIPPETS["realloc_safe"],
                "anchor.realloc_close",
                "programs/state/src/lib.rs",
            )
        )
        results.append(
            self.mutate(
                BENIGN_ANCHOR_SNIPPETS["cpi_typed_program"],
                "anchor.unverified_cpi",
                "programs/transfer/src/lib.rs",
            )
        )

        # TS mutations
        results.append(
            self.mutate(
                BENIGN_TS_SNIPPETS["transfer_scaled"],
                "ts.base_units",
                "src/wallet/transfer.ts",
            )
        )
        results.append(
            self.mutate(
                BENIGN_TS_SNIPPETS["balance_scaled"],
                "ts.lamport_units",
                "src/wallet/balance.ts",
            )
        )
        results.append(
            self.mutate(
                BENIGN_TS_SNIPPETS["address_safe"],
                "ts.address_validation",
                "src/wallet/address.ts",
            )
        )
        results.append(
            self.mutate(
                BENIGN_TS_SNIPPETS["rpc_config"],
                "ts.hardcoded_rpc",
                "src/services/rpc.ts",
            )
        )

        return results
