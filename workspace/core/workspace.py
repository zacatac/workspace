import os
import subprocess
from pathlib import Path
from typing import Optional

from workspace.core.config import ActiveWorkspace, Project
from workspace.core.git import GitError, create_worktree, remove_worktree


class WorkspaceError(Exception):
    """Base exception for workspace operations."""

    pass


def create_workspace(
    project: Project,
    name: str,
    branch: Optional[str] = None,
) -> ActiveWorkspace:
    """Create a new workspace.

    Args:
        project: Project configuration
        name: Name of the workspace
        branch: Optional base branch to create from

    Returns:
        The created workspace configuration

    Raises:
        WorkspaceError: If workspace creation fails
    """
    try:
        # Create worktree directory
        worktree_path = project.root_directory / "worktrees" / f"{project.name}-{name}"
        worktree_path.parent.mkdir(parents=True, exist_ok=True)

        # Create Git worktree
        create_worktree(
            repo_path=project.root_directory,
            worktree_path=worktree_path,
            branch_name=name,
            base_branch=branch,
        )

        return ActiveWorkspace(
            project=project.name,
            name=name,
            path=worktree_path,
            started=False,
        )

    except (GitError, OSError) as e:
        raise WorkspaceError(f"Failed to create workspace: {e}")


def destroy_workspace(workspace: ActiveWorkspace, force: bool = False) -> None:
    """Destroy a workspace.

    Args:
        workspace: Workspace to destroy
        force: Whether to force destroy even if there are changes

    Raises:
        WorkspaceError: If workspace destruction fails
    """
    try:
        # Stop the workspace if it's running
        if workspace.started:
            stop_workspace(workspace)

        # Remove Git worktree
        project_root = workspace.path.parent.parent
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


def start_workspace(workspace: ActiveWorkspace, project: Project) -> None:
    """Start a workspace's infrastructure.

    Args:
        workspace: Workspace to start
        project: Project configuration

    Raises:
        WorkspaceError: If workspace startup fails
    """
    try:
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


def stop_workspace(workspace: ActiveWorkspace, project: Project) -> None:
    """Stop a workspace's infrastructure.

    Args:
        workspace: Workspace to stop
        project: Project configuration

    Raises:
        WorkspaceError: If workspace shutdown fails
    """
    try:
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
) -> subprocess.CompletedProcess:
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
