import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

import petname  # type: ignore
import tomli

from workspace.core.config import (
    ActiveWorkspace,
    Agent,
    GlobalConfig,
    Infrastructure,
    Project,
    ProjectConfig,
)
from workspace.core.git import GitError, create_worktree, list_worktrees, remove_worktree


class WorkspaceError(Exception):
    """Base exception for workspace operations."""

    pass


def create_tmux_session(
    session_name: str,
    start_directory: Path,
    initial_prompt: str | None = None,
) -> bool:
    """Create a new tmux session if it doesn't exist.

    Creates a session with two vertical panes:
    - Left pane: Empty shell
    - Right pane: Running the 'claude' command with optional initial prompt

    Args:
        session_name: Name for the tmux session
        start_directory: Directory to start the session in
        initial_prompt: Optional initial prompt to send to claude

    Returns:
        True if session was created or already exists, False otherwise

    Raises:
        WorkspaceError: If tmux command fails
    """
    try:
        # Check if the session already exists
        result = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True,
            text=True,
        )

        # If session exists, return True
        if result.returncode == 0:
            return True

        # Create a new session
        result = subprocess.run(
            ["tmux", "new-session", "-d", "-s", session_name, "-c", str(start_directory)],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise WorkspaceError(f"Failed to create tmux session: {result.stderr}")

        # Split window vertically
        result = subprocess.run(
            ["tmux", "split-window", "-h", "-t", session_name],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise WorkspaceError(f"Failed to split tmux window: {result.stderr}")

        # Start claude in the right pane, optionally with an initial prompt
        if initial_prompt:
            # Escape quotes and special characters in the prompt
            escaped_prompt = initial_prompt.replace('"', '\\"')
            escaped_prompt = escaped_prompt.replace("'", "\\'")
            escaped_prompt = escaped_prompt.replace(";", "\\;")
            # Send claude command with the prompt as argument
            result = subprocess.run(
                [
                    "tmux",
                    "send-keys",
                    "-t",
                    f"{session_name}.1",
                    f"claude '{escaped_prompt}'",
                    "Enter",
                ],
                capture_output=True,
                text=True,
            )
        else:
            # Start claude without an initial prompt
            result = subprocess.run(
                ["tmux", "send-keys", "-t", f"{session_name}.1", "claude", "Enter"],
                capture_output=True,
                text=True,
            )

        if result.returncode != 0:
            raise WorkspaceError(f"Failed to start claude in tmux pane: {result.stderr}")

        return True

    except subprocess.SubprocessError as e:
        raise WorkspaceError(f"Failed to create tmux session: {e}") from e


def destroy_tmux_session(session_name: str) -> bool:
    """Destroy a tmux session.

    Args:
        session_name: Name of the tmux session to destroy

    Returns:
        True if session was destroyed, False if it didn't exist

    Raises:
        WorkspaceError: If tmux command fails
    """
    try:
        # Check if the session exists
        result = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True,
            text=True,
        )

        # If session doesn't exist, return False
        if result.returncode != 0:
            return False

        # Kill the session
        result = subprocess.run(
            ["tmux", "kill-session", "-t", session_name],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise WorkspaceError(f"Failed to destroy tmux session: {result.stderr}")

        return True

    except subprocess.SubprocessError as e:
        raise WorkspaceError(f"Failed to destroy tmux session: {e}") from e


def attach_to_tmux_session(session_name: str) -> None:
    """Attach to a tmux session.

    This function doesn't actually attach, since we can't control the parent
    process, but it prints the command to attach to the session.

    Args:
        session_name: Name of the tmux session to attach to

    Raises:
        WorkspaceError: If the session doesn't exist
    """
    try:
        # Check if the session exists
        result = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise WorkspaceError(f"Tmux session '{session_name}' doesn't exist")

        # Print the command to attach to the session
        print(f"tmux attach-session -t {shlex.quote(session_name)}")

    except subprocess.SubprocessError as e:
        raise WorkspaceError(f"Failed to attach to tmux session: {e}") from e


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


def find_unused_worktree(project: Project, config: GlobalConfig) -> tuple[str, Path] | None:
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
        for worktree_path, _branch_name in worktrees:
            # Check if this worktree belongs to our project
            worktree_dir = worktree_path.name
            if isinstance(worktree_dir, str) and worktree_dir.startswith(project_prefix):
                # Extract the worktree name from directory name
                worktree_name = worktree_dir[len(project_prefix) :]

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
    branch: str | None = None,
    worktree_name: str | None = None,
    config: GlobalConfig | None = None,
    reuse_worktree: bool = True,
    initial_prompt: str | None = None,
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

        # Create a tmux session for the workspace
        tmux_session_result: str | None = None
        tmux_session_name = f"{project.name}-{worktree_name}"
        try:
            if create_tmux_session(tmux_session_name, worktree_path, initial_prompt):
                tmux_session_result = tmux_session_name
        except WorkspaceError:
            # If tmux session creation fails, we'll continue without it
            pass

        return ActiveWorkspace(
            project=project.name,
            name=name,
            worktree_name=worktree_name,
            path=worktree_path,
            started=False,
            tmux_session=tmux_session_result,
        )

    except (GitError, OSError) as e:
        raise WorkspaceError(f"Failed to create workspace: {e}") from e


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

        # Clean up tmux session if it exists
        if workspace.tmux_session:
            from contextlib import suppress

            with suppress(WorkspaceError):
                destroy_tmux_session(workspace.tmux_session)

        # Clean up workspace directory
        if workspace.path.exists():
            for root, dirs, files in os.walk(workspace.path, topdown=False):
                for name in files:
                    (Path(root) / name).unlink()
                for name in dirs:
                    (Path(root) / name).rmdir()
            workspace.path.rmdir()

    except (GitError, OSError) as e:
        raise WorkspaceError(f"Failed to destroy workspace: {e}") from e


def load_project_config(project: Project) -> ProjectConfig:
    """Load the ProjectConfig from the project's .workspace.toml file.

    Args:
        project: The project to load the config for

    Returns:
        The loaded ProjectConfig

    Raises:
        WorkspaceError: If the config file doesn't exist or can't be loaded
    """
    try:
        config_path = project.root_directory / ".workspace.toml"
        if not config_path.exists():
            raise WorkspaceError(f"Project config file not found at {config_path}")

        with open(config_path, "rb") as f:
            config_data = tomli.load(f)

        # Extract the sections we need
        project_data = config_data.get("project", {})
        infrastructure_data = config_data.get("infrastructure", {})
        agent_data = config_data.get("agent", {})

        # Create Infrastructure object if data exists
        infrastructure = Infrastructure(
            start=infrastructure_data.get("start", "echo 'No start command defined'"),
            stop=infrastructure_data.get("stop", "echo 'No stop command defined'"),
            test=infrastructure_data.get("test"),
        )

        # Return the config
        return ProjectConfig(
            name=project_data.get("name", project.name),
            infrastructure=infrastructure,
            agent=Agent(**agent_data) if agent_data else None,
        )

    except Exception as e:
        raise WorkspaceError(f"Failed to load project config: {e}") from e


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

        # Load the project config from the project's .workspace.toml file
        project_config = load_project_config(project)

        # Check if infrastructure configuration exists
        if not project_config.infrastructure:
            raise WorkspaceError("No infrastructure configuration found for project")

        # Run the start command in the workspace directory
        result = subprocess.run(
            project_config.infrastructure.start,
            shell=True,
            cwd=workspace.path,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise WorkspaceError(f"Failed to start workspace infrastructure: {result.stderr}")

        workspace.started = True

    except subprocess.SubprocessError as e:
        raise WorkspaceError(f"Failed to start workspace: {e}") from e


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

        # Load the project config from the project's .workspace.toml file
        project_config = load_project_config(project)

        # Check if infrastructure configuration exists
        if not project_config.infrastructure:
            raise WorkspaceError("No infrastructure configuration found for project")

        # Run the stop command in the workspace directory
        result = subprocess.run(
            project_config.infrastructure.stop,
            shell=True,
            cwd=workspace.path,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise WorkspaceError(f"Failed to stop workspace infrastructure: {result.stderr}")

        workspace.started = False

    except subprocess.SubprocessError as e:
        raise WorkspaceError(f"Failed to stop workspace: {e}") from e


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
        raise WorkspaceError(f"Failed to run command in workspace: {e}") from e


def attach_to_workspace_tmux(workspace: ActiveWorkspace) -> None:
    """Attach to a workspace's tmux session.

    Args:
        workspace: Workspace to attach to

    Raises:
        WorkspaceError: If the workspace has no tmux session or it doesn't exist
    """
    if not workspace.tmux_session:
        raise WorkspaceError(f"Workspace '{workspace.name}' has no associated tmux session")

    attach_to_tmux_session(workspace.tmux_session)


def switch_workspace(
    workspace: ActiveWorkspace, config: GlobalConfig, tmux_attach: bool = True
) -> None:
    """Switch to a workspace by changing directory and optionally attaching to tmux session.

    Args:
        workspace: Workspace to switch to
        config: Global configuration to find the associated project
        tmux_attach: Whether to attach to the tmux session (if one exists)

    Raises:
        WorkspaceError: If workspace switching fails
    """
    try:
        # Verify the workspace path exists
        if not workspace.path.exists():
            raise WorkspaceError(f"Workspace directory not found at {workspace.path}")

        # Change directory to the workspace path
        # Since we can't actually change the directory of the parent process from here,
        # we print the path to stdout so the wrapper script or shell can handle it
        print(f"cd {workspace.path}")

        # If requested and a tmux session exists, attach to it
        if tmux_attach and workspace.tmux_session:
            # Create the session if it doesn't exist
            if not create_tmux_session(workspace.tmux_session, workspace.path):
                # If session creation failed, update the workspace to note that
                workspace.tmux_session = None
                return

            # Print the command to attach to the session
            attach_to_tmux_session(workspace.tmux_session)

    except Exception as e:
        raise WorkspaceError(f"Failed to switch to workspace: {e}") from e
