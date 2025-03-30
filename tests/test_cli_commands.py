"""Tests for CLI commands."""

import os
from pathlib import Path
from typing import Generator

import pytest
from typer.testing import CliRunner

from workspace.cli.main import app
from workspace.core.config import GlobalConfig, Project


class TestCliCommands:
    """Test class for CLI commands."""

    @pytest.fixture(autouse=True)
    def setup_runner(self) -> Generator[None, None, None]:
        """Set up CLI runner and working directory for each test."""
        self.runner = CliRunner()
        # Save original directory to restore later
        self.original_dir = os.getcwd()
        yield
        # Restore original directory
        os.chdir(self.original_dir)

    def test_list_command(self, temp_workspace_dir: Path, monkeypatch):
        """Test the list command."""
        # Change to example project directory
        os.chdir(temp_workspace_dir)

        # Mock GlobalConfig to return our test config
        def mock_global_config(*args, **kwargs):
            return GlobalConfig()

        monkeypatch.setattr("workspace.cli.main.GlobalConfig", mock_global_config)

        # Run the list command
        result = self.runner.invoke(app, ["list"])

        # Verify it ran successfully
        assert result.exit_code == 0
        assert "Active Workspaces" in result.stdout

    def test_create_command(self, temp_workspace_dir: Path, monkeypatch):
        """Test the create command."""
        # Change to example project directory
        os.chdir(temp_workspace_dir)

        # Mock get_project to return our example project
        def mock_get_project(*args, **kwargs):
            return Project(
                name="example",
                root_directory=temp_workspace_dir,
                infrastructure={
                    "start": "echo 'Starting infrastructure'",
                    "stop": "echo 'Stopping infrastructure'",
                },
            )

        monkeypatch.setattr("workspace.cli.main.get_project", mock_get_project)

        # Run the create command
        result = self.runner.invoke(app, ["create", "test-feature"])

        # Verify output contains expected message
        assert result.exit_code == 0
        assert "Creating workspace" in result.stdout
        assert "test-feature" in result.stdout
        assert "example" in result.stdout

    def test_start_command(self, temp_workspace_dir: Path, monkeypatch):
        """Test the start command."""
        # Change to example project directory
        os.chdir(temp_workspace_dir)

        # Run with a non-existent workspace - should fail
        result = self.runner.invoke(app, ["start", "non-existent"])
        assert result.exit_code != 0
        assert "not found" in result.stdout

    def test_stop_command(self, temp_workspace_dir: Path, monkeypatch):
        """Test the stop command."""
        # Change to example project directory
        os.chdir(temp_workspace_dir)

        # Run with a non-existent workspace - should fail
        result = self.runner.invoke(app, ["stop", "non-existent"])
        assert result.exit_code != 0
        assert "not found" in result.stdout

    def test_destroy_command_with_confirmation(self, temp_workspace_dir: Path, monkeypatch):
        """Test the destroy command with confirmation."""
        # Change to example project directory
        os.chdir(temp_workspace_dir)

        # Run destroy command with confirmation (saying no)
        result = self.runner.invoke(app, ["destroy", "test-feature"], input="n\n")
        assert result.exit_code != 0
        assert "Aborted" in result.stdout

        # Run destroy command with force flag (no confirmation)
        result = self.runner.invoke(app, ["destroy", "test-feature", "--force"])
        # Will fail because workspace doesn't exist, but it shouldn't ask for confirmation
        assert "Are you sure" not in result.stdout
