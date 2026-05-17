import pytest
import os
import tempfile
import shutil
from app.agents.tools.commands import CommandTools
from app.agents.tools.policy import PolicyMode

@pytest.fixture
def temp_project():
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)

def test_command_tools_initialization(temp_project):
    tools = CommandTools(project_path=temp_project)
    assert tools.project_path == temp_project
    assert tools.timeout == 30

def test_run_command_success(temp_project):
    tools = CommandTools(project_path=temp_project)
    # Use 'ls' as a basic command
    result = tools.run_command("ls", ["-a"])
    assert "." in result
    assert ".." in result

def test_run_command_cwd(temp_project):
    # Create a file in temp_project
    test_file = os.path.join(temp_project, "test.txt")
    with open(test_file, "w") as f:
        f.write("hello")
    
    tools = CommandTools(project_path=temp_project)
    result = tools.run_command("ls")
    assert "test.txt" in result

def test_policy_blocked_command(temp_project):
    tools = CommandTools(project_path=temp_project, policy_mode=PolicyMode.GUARDED)
    result = tools.run_command("sudo", ["ls"])
    assert "Error: Command 'sudo' is blocked" in result

def test_policy_blocked_rm_rf(temp_project):
    tools = CommandTools(project_path=temp_project, policy_mode=PolicyMode.GUARDED)
    result = tools.exec_command("rm -rf /")
    assert "Error: Recursive or forced deletion is not allowed" in result

def test_policy_confirmation_required(temp_project):
    tools = CommandTools(project_path=temp_project, policy_mode=PolicyMode.GUARDED)
    result = tools.run_command("git", ["push"])
    assert "requires manual user confirmation" in result

def test_strict_mode(temp_project):
    tools = CommandTools(project_path=temp_project, policy_mode=PolicyMode.STRICT)
    # Allowed
    result = tools.run_command("ls")
    assert "Error" not in result
    # Not allowed
    result = tools.run_command("whoami")
    assert "not in the allowlist" in result

def test_output_truncation(temp_project):
    tools = CommandTools(project_path=temp_project, max_output_length=10)
    result = tools.run_command("echo", ["this is a long message"])
    assert "truncated" in result
    assert len(result) > 10 # Includes truncation message

def test_timeout_handling(temp_project):
    tools = CommandTools(project_path=temp_project, timeout=1)
    # 'sleep 2' should timeout
    result = tools.run_command("sleep", ["2"])
    assert "timed out after 1s" in result
