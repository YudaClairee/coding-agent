import pytest

from app.agents.tools.commands import CommandTools
from app.agents.tools.policy import PolicyMode


def test_exec_command_rejects_dangerous_metacharacters(temp_project):
    tools = CommandTools(project_path=temp_project, policy_mode=PolicyMode.GUARDED)
    # Contains a semicolon which should be rejected before policy evaluation
    result = tools.exec_command("echo safe; rm -rf /")
    assert "forbidden shell metacharacters" in result


def test_exec_command_parsing_error_handled(monkeypatch, temp_project):
    """Ensure a bad quoting pattern is reported as a parse error, not executed."""
    tools = CommandTools(project_path=temp_project, policy_mode=PolicyMode.GUARDED)
    # Unbalanced quote should make shlex.split fail
    result = tools.exec_command("echo 'unbalanced")
    assert "Failed to parse command" in result


def test_exec_command_policy_applied_after_normalization(temp_project):
    tools = CommandTools(project_path=temp_project, policy_mode=PolicyMode.STRICT)
    # "ls" is allowed in STRICT mode; ensure it still works via exec_command
    result = tools.exec_command("ls")
    assert "Error" not in result