"""Tests for workspace creation functionality."""

import os
from pathlib import Path

import pytest

from workspace.core.config import GlobalConfig, Project
from workspace.core.workspace import create_workspace, destroy_workspace


class TestWorkspaceCreation:
    """Test class for workspace creation operations."""

    def test_create_workspace(self, example_project_config: Project, global_config: GlobalConfig):
        """Test creating a workspace."""
        # Add project to global config
        global_config.projects.append(example_project_config)
        
        # Create a new workspace
        workspace = create_workspace(
            project=example_project_config, name="test-feature", branch=None
        )

        # Verify workspace was created
        assert workspace.name == "test-feature"
        assert workspace.project == "example"
        assert workspace.path.exists()
        assert workspace.started is False

        # Verify worktree directory structure
        worktree_path = example_project_config.root_directory.parent / "worktrees" / "example-test-feature"
        assert workspace.path == worktree_path
        assert (worktree_path / "main.py").exists()
        assert (worktree_path / ".workspace.toml").exists()

        # Clean up
        destroy_workspace(workspace, global_config)
        assert not workspace.path.exists()

    def test_create_workspace_with_base_branch(
        self, example_project_config: Project, global_config: GlobalConfig, temp_workspace_dir: Path
    ):
        """Test creating a workspace from a specific base branch."""
        # Add project to global config
        global_config.projects.append(example_project_config)
        
        # Create a development branch first
        os.chdir(temp_workspace_dir)
        os.system("git checkout -b development")
        os.system("echo 'Development branch' > dev.txt")
        os.system("git add dev.txt")
        os.system("git commit -m 'Add development file'")

        # Create a new workspace based on the development branch
        workspace = create_workspace(
            project=example_project_config, name="feature-from-dev", branch="development"
        )

        # Verify workspace was created with content from development branch
        assert workspace.name == "feature-from-dev"
        assert (workspace.path / "dev.txt").exists()

        # Clean up
        destroy_workspace(workspace, global_config)

    def test_create_multiple_workspaces(
        self, example_project_config: Project, global_config: GlobalConfig
    ):
        """Test creating multiple workspaces simultaneously."""
        # Add project to global config
        global_config.projects.append(example_project_config)
        
        workspaces = []

        # Create multiple workspaces
        for i in range(3):
            workspace = create_workspace(
                project=example_project_config, name=f"feature-{i}", branch=None
            )
            workspaces.append(workspace)
            # Add workspace to global config
            global_config.active_workspaces.append(workspace)

        # Verify we have the expected number of workspaces
        assert len(global_config.active_workspaces) == 3

        # Clean up all workspaces
        for workspace in workspaces:
            destroy_workspace(workspace, global_config)
            # Also remove from active workspaces list
            global_config.active_workspaces.remove(workspace)
