"""Tests for tmux process detection functionality."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from workspace.core.config import (
    ActiveWorkspace,
    ClaudeProcess,
    GlobalConfig,
    ProcessStatus,
    Project,
)
from workspace.core.workspace import (
    capture_tmux_pane_content,
    check_completed_claude_processes,
    execute_tmux_command,
    get_claude_process_status,
    get_tmux_pane_processes,
    get_tmux_session_capture_file,
    is_claude_running_in_tmux_session,
    send_command_to_tmux_pane,
    update_claude_process_status,
)


@pytest.fixture
def mock_subprocess():
    """Mock subprocess.run for tmux command testing."""
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        yield mock_run


@pytest.fixture
def test_config():
    """Create a test configuration with a workspace and tmux session."""
    config = GlobalConfig(
        projects=[
            Project(
                name="project1",
                root_directory=Path("/path/to/project1"),
            )
        ],
        active_workspaces=[
            ActiveWorkspace(
                project="project1",
                name="workspace1",
                worktree_name="test-worktree",
                path=Path("/path/to/worktrees/project1-test-worktree"),
                started=False,
                tmux_session="project1-test-worktree",
            )
        ],
    )
    return config


class TestTmuxProcessDetection:
    """Test class for tmux process detection."""

    def test_execute_tmux_command(self, mock_subprocess):
        """Test executing a tmux command."""
        success, stdout, stderr = execute_tmux_command(["tmux", "list-sessions"])
        assert success is True
        assert stdout == "Output"
        assert stderr == ""
        mock_subprocess.assert_called_once()

    def test_get_tmux_pane_processes(self, mock_subprocess):
        """Test getting processes from a tmux pane."""
        # Configure mock to return a valid process list
        mock_subprocess.return_value.stdout = """  PID COMMAND      STAT
  123 bash         Ss
  456 claude       R+"""

        processes = get_tmux_pane_processes("test-session", "1")
        assert len(processes) == 2
        assert processes[0]["pid"] == "123"
        assert processes[0]["command"] == "bash"
        assert processes[0]["status"] == "Ss"
        assert processes[1]["pid"] == "456"
        assert processes[1]["command"] == "claude"
        assert processes[1]["status"] == "R+"

    def test_is_claude_running_in_tmux_session(self, mock_subprocess):
        """Test detecting if Claude is running in a tmux session."""
        # Set up mock to simulate Claude running
        mock_subprocess.return_value.stdout = """  PID COMMAND      STAT
  123 bash         Ss
  456 claude       R+"""

        # Check if Claude is running
        assert is_claude_running_in_tmux_session("test-session") is True

        # Now change the mock to simulate Claude not running
        mock_subprocess.return_value.stdout = """  PID COMMAND      STAT
  123 bash         Ss"""

        # Check again
        assert is_claude_running_in_tmux_session("test-session") is False

    def test_get_claude_process_status(self, mock_subprocess):
        """Test getting Claude process status."""
        # Set up mock to simulate Claude running
        mock_subprocess.return_value.stdout = """  PID COMMAND      STAT
  123 bash         Ss
  456 claude       R+"""

        # Check process status
        assert get_claude_process_status("test-session") == "running"

        # Simulate Claude sleeping
        mock_subprocess.return_value.stdout = """  PID COMMAND      STAT
  123 bash         Ss
  456 claude       S+"""

        # Check process status again
        assert get_claude_process_status("test-session") == "stopped"

        # Simulate Claude completed (no claude process)
        mock_subprocess.return_value.stdout = """  PID COMMAND      STAT
  123 bash         Ss"""

        # Check process status again
        assert get_claude_process_status("test-session") == "completed"

    def test_update_claude_process_status(self, mock_subprocess, test_config):
        """Test updating the Claude process status in a workspace."""
        workspace = test_config.active_workspaces[0]

        # Initialize claude_process
        workspace.claude_process = ClaudeProcess(status=ProcessStatus.NOT_STARTED)

        # Simulate Claude running
        mock_subprocess.return_value.stdout = """  PID COMMAND      STAT
  123 bash         Ss
  456 claude       R+"""

        # Update process status
        status = update_claude_process_status(workspace)
        assert status == "running"
        assert workspace.claude_process.status == ProcessStatus.RUNNING
        assert workspace.claude_process.start_time is not None

        # Simulate Claude completed
        mock_subprocess.return_value.stdout = """  PID COMMAND      STAT
  123 bash         Ss"""

        # Mock the capture_tmux_pane_content function
        with patch("workspace.core.workspace.capture_tmux_pane_content") as mock_capture:
            mock_capture.return_value = Path("/tmp/capture.txt")

            # Update process status again
            status = update_claude_process_status(workspace)
            assert status == "completed"
            assert workspace.claude_process.status == ProcessStatus.COMPLETED
            assert workspace.claude_process.end_time is not None
            assert workspace.claude_process.exit_code == 0
            assert workspace.claude_process.result_file == Path("/tmp/capture.txt")

    def test_check_completed_claude_processes(self, mock_subprocess, test_config):
        """Test checking for completed Claude processes."""
        # Set up the workspace
        workspace = test_config.active_workspaces[0]
        workspace.claude_process = ClaudeProcess(status=ProcessStatus.RUNNING)

        # Simulate all processes running
        with patch("workspace.core.workspace.update_claude_process_status") as mock_update:
            mock_update.return_value = "running"
            completed = check_completed_claude_processes(test_config)
            assert len(completed) == 0

        # Now change the status to completed
        workspace.claude_process.status = ProcessStatus.COMPLETED

        # Simulate one process completed
        with patch("workspace.core.workspace.update_claude_process_status") as mock_update:
            mock_update.return_value = "completed"
            completed = check_completed_claude_processes(test_config)
            assert len(completed) == 1
            assert completed[0].name == "workspace1"

    def test_get_tmux_session_capture_file(self):
        """Test getting the path for capturing tmux pane content."""
        capture_file = get_tmux_session_capture_file("test-session")
        assert capture_file.name == "test-session.txt"
        assert str(capture_file.parent).endswith("/.workspace/sessions")

    @patch("builtins.open", new_callable=MagicMock)
    def test_capture_tmux_pane_content(self, mock_open, mock_subprocess):
        """Test capturing content from a tmux pane."""
        # Mock successful pane capture
        with patch("workspace.core.workspace.get_tmux_session_capture_file") as mock_get_file:
            mock_get_file.return_value = Path("/tmp/test-session.txt")

            result = capture_tmux_pane_content("test-session")
            assert result == Path("/tmp/test-session.txt")
            mock_open.assert_called_once()

    def test_send_command_to_tmux_pane(self, mock_subprocess):
        """Test sending a command to a tmux pane."""
        # Test successful command sending
        result = send_command_to_tmux_pane("test-session", "echo 'hello'")
        assert result is True

        # Test when session doesn't exist
        mock_subprocess.return_value.returncode = 1
        result = send_command_to_tmux_pane("nonexistent-session", "echo 'hello'")
        assert result is False
