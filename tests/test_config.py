"""Tests for configuration functionality."""

import os
from pathlib import Path

import pytest

from workspace.core.config import (
    GlobalConfig,
    Infrastructure,
    Project,
    ProjectConfig,
    ActiveWorkspace,
    Agent,
)
from workspace.core.config_manager import (
    save_global_config,
    load_global_config,
    get_config_dir,
    save_project_config,
    load_project_config,
)


class TestConfiguration:
    """Test class for configuration operations."""

    def test_project_config_parsing(self, temp_workspace_dir: Path):
        """Test parsing project configuration from disk."""
        # Create project config file
        config_path = temp_workspace_dir / ".workspace.toml"
        with open(config_path, "w") as f:
            f.write(
                """
[project]
name = "test-project"

[infrastructure]
start = "docker-compose up -d"
stop = "docker-compose down"
test = "pytest"

[agent]
primary = "npm start"
readonly = "npm run readonly"
            """
            )

        # Read config
        project_config = ProjectConfig(
            name="test-project",
            infrastructure=Infrastructure(
                start="docker-compose up -d",
                stop="docker-compose down",
                test="pytest",
            ),
            agent=Agent(
                primary="npm start",
                readonly="npm run readonly",
            ),
        )

        # Verify config
        assert project_config.name == "test-project"
        assert project_config.infrastructure.start == "docker-compose up -d"
        assert project_config.infrastructure.stop == "docker-compose down"
        assert project_config.infrastructure.test == "pytest"
        assert project_config.agent is not None
        assert project_config.agent.primary == "npm start"
        assert project_config.agent.readonly == "npm run readonly"

    def test_global_config(self):
        """Test global configuration functionality."""
        # Create a global config with projects
        project1 = Project(
            name="project1",
            root_directory=Path("/path/to/project1"),
            infrastructure=None,
            agent=None,
        )

        project2 = Project(
            name="project2",
            root_directory=Path("/path/to/project2"),
            infrastructure=None,
            agent=None,
        )

        global_config = GlobalConfig(projects=[project1, project2], active_workspaces=[])

        # Verify global config
        assert len(global_config.projects) == 2
        assert global_config.projects[0].name == "project1"
        assert global_config.projects[1].name == "project2"
        assert len(global_config.active_workspaces) == 0

        # Test adding an active workspace
        workspace = ActiveWorkspace(
            project="project1",
            name="feature1",
            worktree_name="feature1-worktree",
            path=Path("/path/to/project1/worktrees/project1-feature1-worktree"),
            started=False,
        )
        global_config.active_workspaces.append(workspace)

        assert len(global_config.active_workspaces) == 1
        assert global_config.active_workspaces[0].project == "project1"

    def test_save_global_config_with_none_values(self, monkeypatch, tmp_path):
        """Test saving global config with None values."""
        # Set config dir to temp directory
        monkeypatch.setattr("workspace.core.config_manager.get_config_dir", lambda: tmp_path)

        # Create a config with None values
        project = Project(
            name="project-test",
            root_directory=Path("/path/to/project"),
            infrastructure=None,  # This is None
            agent=None,  # This is None
        )

        workspace = ActiveWorkspace(
            project="project-test",
            name="feature-test",
            worktree_name="feature-test-branch",
            path=Path("/path/to/worktree"),
            started=False,
        )

        config = GlobalConfig(projects=[project], active_workspaces=[workspace], tasks=[])

        # This should not raise an error
        save_global_config(config)

        # Verify the file was created
        config_path = tmp_path / "config.toml"
        assert config_path.exists()

        # Load the config back and check values
        reloaded_config = load_global_config()
        assert len(reloaded_config.projects) == 1
        assert reloaded_config.projects[0].name == "project-test"
        assert reloaded_config.projects[0].infrastructure is None
        assert reloaded_config.projects[0].agent is None

    def test_save_project_config_with_none_values(self, tmp_path):
        """Test saving project config with None values."""
        # Create a project config with minimal values
        project_config = ProjectConfig(
            name="test-project",
            infrastructure=Infrastructure(
                start="echo 'start'",
                stop="echo 'stop'",
                test=None,  # Optional field, explicitly set to None
            ),
            agent=None,  # This is None
        )

        # This should not raise an error
        save_project_config(project_config, tmp_path)

        # Verify the file was created
        config_path = tmp_path / ".workspace.toml"
        assert config_path.exists()

        # Load the config back and check values
        reloaded_config = load_project_config(tmp_path)
        assert reloaded_config is not None
        assert reloaded_config.name == "test-project"
        assert reloaded_config.agent is None
