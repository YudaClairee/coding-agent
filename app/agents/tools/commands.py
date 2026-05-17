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
            return (
                "Error: Command '"
                + command_str
                + "' requires manual user confirmation. This agent is not authorized to run it automatically."
            )

        try:
            result = subprocess.run(
                full_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
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
        """Execute a raw shell command supporting pipes and redirection.

        This function avoids ``shell=True`` by parsing the command string and
        chaining multiple ``subprocess.Popen`` calls for pipeline handling.

        WARNING: Prefer :meth:`run_command` when possible, as it is easier to
        validate and reason about.

        Args:
            command(str): The shell command to execute.

        Returns:
            str: The stdout and stderr output of the command.
        """

        logger.info(f"Executing exec_command: {command} (cwd: {self.project_path})")

        # Policy validation still happens on the raw command string
        is_allowed, error_msg, requires_conf = self.policy.validate(command)
        if not is_allowed:
            logger.warning(f"Command blocked by policy: {command}. Reason: {error_msg}")
            return f"Error: {error_msg}"

        if requires_conf:
            logger.warning(f"Command requires confirmation: {command}")
            return (
                "Error: Command '"
                + command
                + "' requires manual user confirmation. This agent is not authorized to run it automatically."
            )

        processes: list[subprocess.Popen] = []
        stdin_file = None
        stdout_file = None

        try:
            # Split into pipeline segments
            segments = [s.strip() for s in command.split("|") if s.strip()]
            if not segments:
                return "Error: Empty command"

            prev_stdout = None

            for i, segment in enumerate(segments):
                stdin = prev_stdout
                stdout = subprocess.PIPE
                # Only the last process uses a dedicated stderr pipe; earlier ones merge stderr into stdout
                stderr = subprocess.PIPE if i == len(segments) - 1 else subprocess.STDOUT

                # Support a single level of redirection per segment
                parts = shlex.split(segment, posix=True)
                cmd_parts: list[str] = []
                it = iter(parts)
                for token in it:
                    if token == "<":
                        try:
                            filename = next(it)
                        except StopIteration:
                            return "Error: Missing filename after '<'"
                        stdin_file = open(filename, "r")
                    elif token in {">", ">>"}:
                        try:
                            filename = next(it)
                        except StopIteration:
                            return "Error: Missing filename after '>'"
                        mode = "a" if token == ">>" else "w"
                        stdout_file = open(filename, mode)
                    else:
                        cmd_parts.append(token)

                if not cmd_parts:
                    return "Error: Empty pipeline segment"

                # Determine stdin for this process
                if stdin_file is not None and i == 0:
                    stdin = stdin_file
                elif prev_stdout is not None:
                    stdin = prev_stdout

                # Determine stdout for this process
                if stdout_file is not None and i == len(segments) - 1:
                    stdout = stdout_file
                elif i < len(segments) - 1:
                    stdout = subprocess.PIPE

                proc = subprocess.Popen(
                    cmd_parts,
                    stdin=stdin,
                    stdout=stdout,
                    stderr=stderr,
                    text=True,
                    cwd=self.project_path,
                )

                # Close the previous stdout in the parent so we don't leak file descriptors
                if prev_stdout is not None and prev_stdout is not stdin:
                    try:
                        prev_stdout.close()  # type: ignore[call-arg]
                    except Exception:
                        pass

                processes.append(proc)
                prev_stdout = proc.stdout

            # Collect output from the last process
            stdout_data, stderr_data = processes[-1].communicate(timeout=self.timeout)

            # Ensure all earlier processes complete
            for proc in processes[:-1]:
                proc.wait(timeout=self.timeout)

            # Create a simple result-like object to pass into _format_result
            class _Result:
                def __init__(self, stdout: str, stderr: str, returncode: int):
                    self.stdout = stdout
                    self.stderr = stderr
                    self.returncode = returncode

            result = _Result(stdout_data or "", stderr_data or "", processes[-1].returncode)
            return self._format_result(result)  # type: ignore[arg-type]

        except subprocess.TimeoutExpired as e:
            return self._handle_timeout(e, command)
        except Exception as e:
            return self._handle_error(e, command)
        finally:
            # Ensure any opened files are closed
            for f in (stdin_file, stdout_file):
                if f is not None:
                    try:
                        f.close()
                    except Exception:
                        pass

            # Close any remaining stdout/stderr pipes
            for proc in processes:
                for stream in (proc.stdout, proc.stderr):
                    if stream is not None:
                        try:
                            stream.close()
                        except Exception:
                            pass

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