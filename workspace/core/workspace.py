import os
import subprocess
from pathlib import Path
from typing import Any, Optional

import petname  # type: ignore

from workspace.core.config import ActiveWorkspace, GlobalConfig, Project
from workspace.core.git import GitError, create_worktree, remove_worktree


class WorkspaceError(Exception):
    """Base exception for workspace operations."""

    pass


def get_project_for_workspace(workspace: ActiveWorkspace, config: GlobalConfig) -> Project:
    """Get the Project configuration for an ActiveWorkspace.

    Args:
        workspace: The workspace to get the project for
        config: The global configuration

    Returns:
        The associated Project configuration

    Raises:
        WorkspaceError: If the project for the workspace is not found
    """
    for project in config.projects:
        if project.name == workspace.project:
            return project
    raise WorkspaceError(
        f"Project '{workspace.project}' not found for workspace '{workspace.name}'"
    )


def generate_worktree_name() -> str:
    """Generate a friendly, readable worktree name.
    
    Returns:
        A unique, human-readable name for the worktree
    """
    # Generate a readable name with 2 words (adjective + noun)
    return str(petname.generate(words=2, separator="-"))

def create_workspace(
    project: Project,
    name: str,
    branch: Optional[str] = None,
    worktree_name: Optional[str] = None,
) -> ActiveWorkspace:
    """Create a new workspace.

    Args:
        project: Project configuration
        name: Name of the workspace
        branch: Optional base branch to create from
        worktree_name: Optional worktree name, generated if not provided

    Returns:
        The created workspace configuration

    Raises:
        WorkspaceError: If workspace creation fails
    """
    try:
        # Generate or use provided worktree name
        if not worktree_name:
            worktree_name = generate_worktree_name()
            
        # Create worktree directory in the parent directory of the project
        worktrees_dir = project.root_directory.parent / "worktrees"
        worktree_path = worktrees_dir / f"{project.name}-{worktree_name}"
        worktrees_dir.mkdir(parents=True, exist_ok=True)

        # Create Git worktree using the worktree name as the branch name
        # This decouples the workspace name from the branch name
        create_worktree(
            repo_path=project.root_directory,
            worktree_path=worktree_path,
            branch_name=worktree_name,
            base_branch=branch,
        )

        return ActiveWorkspace(
            project=project.name,
            name=name,
            worktree_name=worktree_name,
            path=worktree_path,
            started=False,
        )

    except (GitError, OSError) as e:
        raise WorkspaceError(f"Failed to create workspace: {e}")


def destroy_workspace(
    workspace: ActiveWorkspace, config: GlobalConfig, force: bool = False
) -> None:
    """Destroy a workspace.

    Args:
        workspace: Workspace to destroy
        config: Global configuration to find the associated project
        force: Whether to force destroy even if there are changes

    Raises:
        WorkspaceError: If workspace destruction fails
    """
    try:
        # Stop the workspace if it's running
        if workspace.started:
            stop_workspace(workspace, config)

        # Remove Git worktree
        # Find the project root from the config
        project = get_project_for_workspace(workspace, config)
        project_root = project.root_directory
        remove_worktree(project_root, workspace.path, force)

        # Clean up workspace directory
        if workspace.path.exists():
            for root, dirs, files in os.walk(workspace.path, topdown=False):
                for name in files:
                    (Path(root) / name).unlink()
                for name in dirs:
                    (Path(root) / name).rmdir()
            workspace.path.rmdir()

    except (GitError, OSError) as e:
        raise WorkspaceError(f"Failed to destroy workspace: {e}")


def start_workspace(workspace: ActiveWorkspace, config: GlobalConfig) -> None:
    """Start a workspace's infrastructure.

    Args:
        workspace: Workspace to start
        config: Global configuration to find the associated project

    Raises:
        WorkspaceError: If workspace startup fails
    """
    try:
        project = get_project_for_workspace(workspace, config)
        # Run the start command in the workspace directory
        result = subprocess.run(
            project.infrastructure.start,
            shell=True,
            cwd=workspace.path,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise WorkspaceError(f"Failed to start workspace infrastructure: {result.stderr}")

        workspace.started = True

    except subprocess.SubprocessError as e:
        raise WorkspaceError(f"Failed to start workspace: {e}")


def stop_workspace(workspace: ActiveWorkspace, config: GlobalConfig) -> None:
    """Stop a workspace's infrastructure.

    Args:
        workspace: Workspace to stop
        config: Global configuration to find the associated project

    Raises:
        WorkspaceError: If workspace shutdown fails
    """
    try:
        project = get_project_for_workspace(workspace, config)
        # Run the stop command in the workspace directory
        result = subprocess.run(
            project.infrastructure.stop,
            shell=True,
            cwd=workspace.path,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise WorkspaceError(f"Failed to stop workspace infrastructure: {result.stderr}")

        workspace.started = False

    except subprocess.SubprocessError as e:
        raise WorkspaceError(f"Failed to stop workspace: {e}")


def run_in_workspace(
    workspace: ActiveWorkspace,
    command: list[str],
) -> subprocess.CompletedProcess[Any]:
    """Run a command in a workspace.

    Args:
        workspace: Workspace to run in
        command: Command to run as a list of strings

    Returns:
        The completed process

    Raises:
        WorkspaceError: If command execution fails
    """
    try:
        return subprocess.run(
            command,
            cwd=workspace.path,
            check=True,
        )

    except subprocess.SubprocessError as e:
        raise WorkspaceError(f"Failed to run command in workspace: {e}")
