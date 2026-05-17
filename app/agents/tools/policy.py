import logging
import shlex
from enum import Enum

logger = logging.getLogger(__name__)


class PolicyMode(Enum):
    PERMISSIVE = "permissive"
    GUARDED = "guarded"
    STRICT = "strict"


class CommandPolicy:
    """Policy for validating shell commands."""

    # Commands that are always blocked in Guarded and Strict modes
    DENYLIST: set[str] = {
        "sudo",
        "shutdown",
        "reboot",
        "format",
        "mkfs",
        "dd",
        "chmod",
        "chown",
        "passwd",
        "useradd",
        "userdel",
        "curl",
        "wget",
        "nc",
        "scp",
        "ssh",
        "ftp",
        "telnet",
    }

    # Commands that require user confirmation in Guarded mode
    CONFIRMATION_REQUIRED: set[str] = {
        "git push",
        "npm publish",
        "pnpm publish",
        "yarn publish",
        "docker push",
        "rm -rf",
    }

    # Commands allowed in Strict mode
    ALLOWLIST: set[str] = {
        "python",
        "python3",
        "uv",
        "pytest",
        "ruff",
        "git",
        "pnpm",
        "npm",
        "yarn",
        "ls",
        "pwd",
        "cat",
        "echo",
        "mkdir",
        "touch",
        "grep",
        "find",
        "cd",
    }

    def __init__(self, mode: PolicyMode = PolicyMode.GUARDED):
        self.mode = mode

    def validate(self, command: str) -> tuple[bool, str, bool]:
        """Validate a command against the policy.

        Returns:
            tuple[bool, str, bool]: (is_allowed, error_message, requires_confirmation)
        """
        if self.mode == PolicyMode.PERMISSIVE:
            return True, "", False

        # Basic parsing to get the main program
        try:
            tokens = shlex.split(command)
            if not tokens:
                return False, "Empty command", False

            program = tokens[0]
            # Handle cases like 'VAR=val program'
            if "=" in program and len(tokens) > 1:
                program = tokens[1]

        except Exception as e:
            return False, f"Failed to parse command: {str(e)}", False

        if self.mode == PolicyMode.GUARDED:
            if program in self.DENYLIST:
                return False, f"Command '{program}' is blocked for safety reasons.", False

            # Check for dangerous flags in common commands
            if program == "rm" and any(arg in ["-rf", "-f", "-r"] for arg in tokens):
                return False, "Recursive or forced deletion is not allowed.", False

            # Check for confirmation requirement
            requires_conf = False
            for conf_cmd in self.CONFIRMATION_REQUIRED:
                if command.startswith(conf_cmd):
                    requires_conf = True
                    break

            return True, "", requires_conf

        if self.mode == PolicyMode.STRICT:
            if program not in self.ALLOWLIST:
                return False, f"Command '{program}' is not in the allowlist for strict mode.", False
            return True, "", False

        return True, "", False
