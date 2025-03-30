"""Tests for workspace operations functionality."""

import os
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from workspace.core.config import GlobalConfig, Project, ProjectConfig, Infrastructure, Agent
from workspace.core.workspace import (
    create_workspace,
    destroy_workspace,
    run_in_workspace,
    start_workspace,
    stop_workspace,
    load_project_config,
    create_tmux_session,
    destroy_tmux_session,
    attach_to_tmux_session,
    attach_to_workspace_tmux,
    switch_workspace,
)


class TestWorkspaceOperations:
    """Test class for workspace operations."""

    @pytest.fixture(autouse=True)
    def setup_workspace(self, example_project_config: Project, global_config: GlobalConfig):
        """Set up a workspace for each test and clean it up afterwards."""
        # Add the project to global config
        global_config.projects.append(example_project_config)

        # Create a test workspace
        self.workspace = create_workspace(
            project=example_project_config, name="test-operations", branch=None
        )
        global_config.active_workspaces.append(self.workspace)

        yield

        # Clean up
        if self.workspace in global_config.active_workspaces:
            global_config.active_workspaces.remove(self.workspace)

        try:
            destroy_workspace(self.workspace, global_config, force=True)
        except Exception:
            # If cleanup fails, log but don't fail the test
            print("Failed to clean up workspace")

    @patch("workspace.core.workspace.load_project_config")
    def test_start_workspace(self, mock_load_config, global_config: GlobalConfig):
        """Test starting a workspace."""
        # Mock the return value of load_project_config
        mock_config = ProjectConfig(
            name="example",
            infrastructure=Infrastructure(
                start="echo 'Starting infrastructure'",
                stop="echo 'Stopping infrastructure'",
                test="echo 'Running tests'",
            ),
            agent=Agent(
                primary="echo 'Running primary agent'",
                readonly="echo 'Running readonly agent'",
            ),
        )
        mock_load_config.return_value = mock_config

        # Start the workspace
        start_workspace(self.workspace, global_config)

        # Verify the workspace is started
        assert self.workspace.started is True

    @patch("workspace.core.workspace.load_project_config")
    def test_stop_workspace(self, mock_load_config, global_config: GlobalConfig):
        """Test stopping a workspace."""
        # Mock the return value of load_project_config
        mock_config = ProjectConfig(
            name="example",
            infrastructure=Infrastructure(
                start="echo 'Starting infrastructure'",
                stop="echo 'Stopping infrastructure'",
                test="echo 'Running tests'",
            ),
            agent=Agent(
                primary="echo 'Running primary agent'",
                readonly="echo 'Running readonly agent'",
            ),
        )
        mock_load_config.return_value = mock_config

        # Start the workspace first
        start_workspace(self.workspace, global_config)
        assert self.workspace.started is True

        # Stop the workspace
        stop_workspace(self.workspace, global_config)

        # Verify the workspace is stopped
        assert self.workspace.started is False

    def test_run_in_workspace(self):
        """Test running a command in a workspace."""
        # Create a test file in the workspace
        test_file = self.workspace.path / "test.txt"
        with open(test_file, "w") as f:
            f.write("Test content")

        # Run a command in the workspace
        result = run_in_workspace(self.workspace, ["cat", "test.txt"])

        # Verify the command ran successfully
        assert result.returncode == 0

    def test_workspace_isolation(
        self, example_project_config: Project, global_config: GlobalConfig
    ):
        """Test that changes in one workspace don't affect others."""
        # Create a second workspace
        workspace2 = create_workspace(
            project=example_project_config, name="test-isolation", branch=None
        )
        global_config.active_workspaces.append(workspace2)

        try:
            # Make changes in the first workspace
            test_file = self.workspace.path / "unique.txt"
            with open(test_file, "w") as f:
                f.write("Unique to workspace 1")

            # Verify the file doesn't exist in the second workspace
            assert not (workspace2.path / "unique.txt").exists()
        finally:
            # Clean up the second workspace
            if workspace2 in global_config.active_workspaces:
                global_config.active_workspaces.remove(workspace2)
            destroy_workspace(workspace2, global_config, force=True)

    @patch("subprocess.run")
    def test_tmux_session_creation(self, mock_run, example_project_config: Project):
        """Test that a workspace creates a tmux session."""
        # Mock subprocess.run to return success for tmux commands
        mock_run.return_value = MagicMock(returncode=0)

        # Create a workspace which should create a tmux session
        workspace = create_workspace(project=example_project_config, name="test-tmux", branch=None)

        # Verify the workspace has a tmux session name
        assert workspace.tmux_session is not None
        assert workspace.tmux_session == f"{example_project_config.name}-{workspace.worktree_name}"

        # Verify tmux commands were called
        mock_run.assert_any_call(
            ["tmux", "has-session", "-t", workspace.tmux_session],
            capture_output=True,
            text=True,
        )

    @patch("subprocess.run")
    def test_tmux_session_attachment(
        self, mock_run, example_project_config: Project, global_config: GlobalConfig
    ):
        """Test attaching to a workspace's tmux session."""
        # Mock subprocess.run to return success for tmux commands
        mock_run.return_value = MagicMock(returncode=0)

        # Create a workspace with a tmux session
        workspace = create_workspace(
            project=example_project_config, name="test-tmux-attach", branch=None
        )

        # Mock print to capture output
        with patch("builtins.print") as mock_print:
            # Switch to the workspace with tmux_attach=True
            switch_workspace(workspace, global_config, tmux_attach=True)

            # Verify print was called with cd command and tmux attach command
            mock_print.assert_any_call(f"cd {workspace.path}")
            mock_print.assert_any_call(f"tmux attach-session -t {workspace.tmux_session}")

    @patch("subprocess.run")
    def test_tmux_session_destruction(
        self, mock_run, example_project_config: Project, global_config: GlobalConfig
    ):
        """Test that destroying a workspace also destroys its tmux session."""
        # Mock subprocess.run to return success for tmux commands
        mock_run.return_value = MagicMock(returncode=0)

        # Create a workspace with a tmux session
        workspace = create_workspace(
            project=example_project_config, name="test-tmux-destroy", branch=None
        )

        # Verify the workspace has a tmux session
        assert workspace.tmux_session is not None

        # Destroy the workspace
        destroy_workspace(workspace, global_config)

        # Verify tmux kill-session was called
        mock_run.assert_any_call(
            ["tmux", "kill-session", "-t", workspace.tmux_session],
            capture_output=True,
            text=True,
        )
