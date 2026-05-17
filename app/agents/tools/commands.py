import logging
import shlex
import subprocess

from agno.tools import Toolkit

from app.agents.tools.policy import CommandPolicy, PolicyMode

logger = logging.getLogger(__name__)


class CommandTools(Toolkit):
    """Tools for executing shell commands."""

    def __init__(
        self,
        project_path: str | None = None,
        timeout: int = 30,
        max_output_length: int = 10000,
        policy_mode: PolicyMode = PolicyMode.GUARDED,
    ):
        self.project_path = project_path
        self.timeout = timeout
        self.max_output_length = max_output_length
        self.policy = CommandPolicy(mode=policy_mode)
        super().__init__(name="commands", tools=[self.run_command, self.exec_command])

    def run_command(self, program: str, args: list[str] | None = None) -> str:
        """Execute a program with arguments. This is the preferred way to run commands.

        Args:
            program(str): The program to run (e.g., 'ls', 'git', 'python').
            args(list[str], optional): List of arguments for the program.

        Returns:
            str: The stdout and stderr output of the command.
        """
        args = args or []
        full_command = [program] + args
        command_str = " ".join(shlex.quote(arg) for arg in full_command)

        logger.info(f"Executing run_command: {command_str} (cwd: {self.project_path})")

        # Policy validation
        is_allowed, error_msg, requires_conf = self.policy.validate(command_str)
        if not is_allowed:
            logger.warning(f"Command blocked by policy: {command_str}. Reason: {error_msg}")
            return f"Error: {error_msg}"

        if requires_conf:
            logger.warning(f"Command requires confirmation: {command_str}")
            return f"Error: Command '{command_str}' requires manual user confirmation. This agent is not authorized to run it automatically."

        try:
            result = subprocess.run(
                full_command,
                shell=False,  # Security: Disable shell
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.project_path,
            )
            return self._format_result(result)

        except subprocess.TimeoutExpired as e:
            return self._handle_timeout(e, command_str)
        except Exception as e:
            return self._handle_error(e, command_str)

    def exec_command(self, command: str) -> str:
        """Execute a raw shell command. Use run_command instead if possible.
        Only use this if you need shell features like pipes (|) or redirection (>).

        Args:
            command(str): The shell command to execute.

        Returns:
            str: The stdout and stderr output of the command.
        """
        logger.info(f"Executing exec_command: {command} (cwd: {self.project_path})")

        # Policy validation
        is_allowed, error_msg, requires_conf = self.policy.validate(command)
        if not is_allowed:
            logger.warning(f"Command blocked by policy: {command}. Reason: {error_msg}")
            return f"Error: {error_msg}"

        if requires_conf:
            logger.warning(f"Command requires confirmation: {command}")
            return f"Error: Command '{command}' requires manual user confirmation. This agent is not authorized to run it automatically."

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.project_path,
            )
            return self._format_result(result)

        except subprocess.TimeoutExpired as e:
            return self._handle_timeout(e, command)
        except Exception as e:
            return self._handle_error(e, command)

    def _format_result(self, result: subprocess.CompletedProcess) -> str:
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        exit_code = result.returncode

        output_parts = []
        if stdout:
            output_parts.append(stdout)
        if stderr:
            output_parts.append(f"STDERR:\n{stderr}")
        if exit_code != 0:
            output_parts.append(f"Exit code: {exit_code}")

        output = "\n".join(output_parts) or "(no output)"

        if len(output) > self.max_output_length:
            trunc_msg = f"\n... (output truncated, total length: {len(output)} chars)"
            output = output[: self.max_output_length] + trunc_msg

        return output

    def _handle_timeout(self, e: subprocess.TimeoutExpired, command: str) -> str:
        logger.warning(f"Command timed out: {command}")
        output = f"Error: Command timed out after {self.timeout}s"
        if e.stdout:
            output += f"\nPartial STDOUT:\n{e.stdout.decode() if isinstance(e.stdout, bytes) else e.stdout}"
        if e.stderr:
            output += f"\nPartial STDERR:\n{e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr}"
        return output

    def _handle_error(self, e: Exception, command: str) -> str:
        logger.error(f"Failed to execute command: {command}. Error: {str(e)}")
        return f"Error: Failed to execute command: {str(e)}"
