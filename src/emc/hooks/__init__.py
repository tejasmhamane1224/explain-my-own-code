"""Git hook management (pre-commit and commit-msg)."""

from emc.hooks.manager import (
    COMMIT_MSG_SCRIPT,
    PRE_COMMIT_SCRIPT,
    ForeignHookError,
    HookError,
    HookInstallResult,
    HookUninstallResult,
    get_git_hooks_dir,
    handle_commit_msg_hook,
    install_hooks,
    uninstall_hooks,
)

__all__ = [
    "COMMIT_MSG_SCRIPT",
    "PRE_COMMIT_SCRIPT",
    "ForeignHookError",
    "HookError",
    "HookInstallResult",
    "HookUninstallResult",
    "get_git_hooks_dir",
    "handle_commit_msg_hook",
    "install_hooks",
    "uninstall_hooks",
]
