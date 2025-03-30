"""Fixtures for tests."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from workspace.core.config import GlobalConfig, Project, ProjectConfig, Infrastructure, Agent


@pytest.fixture
def temp_workspace_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for testing workspaces with a git repo."""
    # Copy example project to temp directory
    example_project_dir = Path(__file__).parent / "fixtures" / "example_project"
    workspace_dir = tmp_path / "example_project"
    shutil.copytree(example_project_dir, workspace_dir)

    # Initialize git repo
    os.chdir(workspace_dir)
    subprocess.run(["git", "init"], check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], check=True)

    return workspace_dir


@pytest.fixture
def example_project_config(temp_workspace_dir: Path) -> Project:
    """Create an example project configuration."""
    return Project(
        name="example",
        root_directory=temp_workspace_dir,
        infrastructure=None,
        agent=None,
    )


@pytest.fixture
def example_project_config_with_infra(temp_workspace_dir: Path) -> ProjectConfig:
    """Create an example project configuration with infrastructure and agent settings."""
    return ProjectConfig(
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


@pytest.fixture
def global_config() -> GlobalConfig:
    """Create a global configuration for testing."""
    return GlobalConfig(projects=[], active_workspaces=[])
