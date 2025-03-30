import os
import subprocess
from pathlib import Path
from typing import Any, Optional

import petname  # type: ignore

from workspace.core.config import ActiveWorkspace, GlobalConfig, Project
from workspace.core.git import GitError, create_worktree, list_worktrees, remove_worktree


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

def find_unused_worktree(
    project: Project, 
    config: GlobalConfig
) -> Optional[tuple[str, Path]]:
    """Find an unused worktree that can be repurposed.
    
    Args:
        project: Project configuration
        config: Global configuration
        
    Returns:
        Tuple of (worktree_name, path) if an unused worktree is found, None otherwise
    """
    # Get all worktrees for the project
    try:
        worktrees_dir = project.root_directory.parent / "worktrees"
        if not worktrees_dir.exists():
            return None
            
        # Get list of all existing worktrees
        worktrees = list_worktrees(project.root_directory)
        
        # Get all active workspace paths
        active_workspace_paths = {ws.path for ws in config.active_workspaces}
        
        # Find worktrees that belong to this project and aren't in active workspaces
        project_prefix = f"{project.name}-"
        for worktree_path, branch_name in worktrees:
            # Check if this worktree belongs to our project
            worktree_dir = worktree_path.name
            if isinstance(worktree_dir, str) and worktree_dir.startswith(project_prefix):
                # Extract the worktree name from directory name
                worktree_name = worktree_dir[len(project_prefix):]
                
                # If this worktree isn't used by any active workspace, it's available
                if worktree_path not in active_workspace_paths:
                    return (worktree_name, worktree_path)
        
        return None
    except (GitError, OSError):
        # If there's any error, just return None
        return None

def create_workspace(
    project: Project,
    name: str,
    branch: Optional[str] = None,
    worktree_name: Optional[str] = None,
    config: Optional[GlobalConfig] = None,
    reuse_worktree: bool = True,
) -> ActiveWorkspace:
    """Create a new workspace.

    Args:
        project: Project configuration
        name: Name of the workspace
        branch: Optional base branch to create from
        worktree_name: Optional worktree name, generated if not provided
        config: Global configuration to help find unused worktrees
        reuse_worktree: Whether to try reusing an existing unused worktree

    Returns:
        The created workspace configuration

    Raises:
        WorkspaceError: If workspace creation fails
    """
    try:
        worktree_path = None
        
        # Try to reuse an existing worktree if requested and config is provided
        if reuse_worktree and config and not worktree_name:
            unused_worktree = find_unused_worktree(project, config)
            if unused_worktree:
                worktree_name, worktree_path = unused_worktree
        
        # Generate or use provided worktree name if we didn't find an unused one
        if not worktree_name:
            worktree_name = generate_worktree_name()
        
        # If we don't have a worktree path yet, create a new one
        if not worktree_path:
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
