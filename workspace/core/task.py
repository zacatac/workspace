from workspace.core.agent import (
    AgentError,
    analyze_task_with_agent,
    load_task_plan,
    save_task_plan,
    update_task_plan,
)
from workspace.core.config import GlobalConfig, Project, SubTask, Task, TaskType
from workspace.core.workspace import create_workspace, destroy_workspace


class TaskError(Exception):
    """Base exception for task operations."""

    pass


def create_task_plan(
    project: Project, task_description: str, agent_command: str | None = None
) -> Task:
    """Create a task plan using agent analysis.

    Args:
        project: The project for this task
        task_description: The user's description of the task
        agent_command: Optional command to run the agent

    Returns:
        The created task plan

    Raises:
        TaskError: If task plan creation fails
    """
    try:
        # Use agent to analyze task and create structured task
        task = analyze_task_with_agent(
            task_description=task_description, project=project, agent_command=agent_command
        )

        # Save task plan for user review
        save_task_plan(task)

        return task

    except AgentError as e:
        raise TaskError(f"Failed to create task plan: {e}") from e


def confirm_task_plan(task_id: str, config: GlobalConfig) -> Task:
    """Confirm a task plan, adding it to global config.

    Args:
        task_id: The task ID to confirm
        config: The global configuration

    Returns:
        The confirmed task

    Raises:
        TaskError: If task plan confirmation fails
    """
    try:
        # Load task plan
        task = load_task_plan(task_id)

        # Update status
        task.status = "in_progress"

        # Add task to global config
        config.tasks.append(task)

        # Update task plan file
        update_task_plan(task)

        return task

    except AgentError as e:
        raise TaskError(f"Failed to confirm task plan: {e}") from e


def get_task_by_id(task_id: str, config: GlobalConfig) -> Task | None:
    """Get a task by ID.

    Args:
        task_id: The task ID
        config: The global configuration

    Returns:
        The task if found, None otherwise
    """
    for task in config.tasks:
        if task.id == task_id:
            return task
    return None


def get_ready_subtasks(task: Task) -> list[SubTask]:
    """Get subtasks that are ready to be worked on.

    Args:
        task: The task

    Returns:
        List of subtasks that are ready to be worked on
    """
    # Build set of completed subtask IDs
    completed = {st.id for st in task.subtasks if st.status == "completed"}

    # Find subtasks that are pending and have all dependencies completed
    ready = []
    for subtask in task.subtasks:
        if subtask.status == "pending" and all(dep in completed for dep in subtask.dependencies):
            ready.append(subtask)

    return ready


def execute_subtask(task: Task, subtask_id: str, config: GlobalConfig) -> SubTask:
    """Prepare a subtask for execution.

    Args:
        task: The task
        subtask_id: The subtask ID to execute
        config: The global configuration

    Returns:
        The updated subtask

    Raises:
        TaskError: If subtask execution fails
    """
    try:
        # Get project
        project_name = task.project
        project = None
        for p in config.projects:
            if p.name == project_name:
                project = p
                break

        if not project:
            raise TaskError(f"Project {project_name} not found")

        # Find the subtask
        subtask = None
        for st in task.subtasks:
            if st.id == subtask_id:
                subtask = st
                break

        if not subtask:
            raise TaskError(f"Subtask {subtask_id} not found")

        if subtask.status != "pending":
            raise TaskError(f"Subtask {subtask_id} is not pending")

        # Check if dependencies are met
        completed = {st.id for st in task.subtasks if st.status == "completed"}
        if not all(dep in completed for dep in subtask.dependencies):
            raise TaskError(f"Not all dependencies for subtask {subtask_id} are completed")

        # Update subtask status
        subtask.status = "in_progress"

        # Prepare prompt with subtask description
        subtask_prompt = f"Subtask: {subtask.name}\n\n{subtask.description}"

        # For sequential tasks, reuse the existing workspace if any
        if task.task_type == TaskType.SEQUENTIAL:
            # Check if any workspace exists for this task
            existing_workspace = None
            workspace_name = f"task-{task.id}"

            for ws in config.active_workspaces:
                if ws.name == workspace_name and ws.project == project.name:
                    existing_workspace = ws
                    break

            if existing_workspace:
                # Reuse existing workspace
                subtask.workspace_name = existing_workspace.name
                subtask.worktree_name = existing_workspace.worktree_name

                # If there's a tmux session, recreate it with the prompt
                if existing_workspace.tmux_session:
                    from contextlib import suppress

                    from workspace.core.workspace import (
                        WorkspaceError,
                        create_tmux_session,
                        destroy_tmux_session,
                    )

                    # Destroy existing session (ignore errors)
                    with suppress(WorkspaceError):
                        destroy_tmux_session(existing_workspace.tmux_session)
                    # Create new session with initial prompt
                    create_tmux_session(
                        existing_workspace.tmux_session, existing_workspace.path, subtask_prompt
                    )
            else:
                # Create new workspace for sequential task with initial prompt
                workspace = create_workspace(
                    project=project,
                    name=workspace_name,
                    config=config,
                    initial_prompt=subtask_prompt,
                )

                # Add workspace to global config if not already there
                if workspace not in config.active_workspaces:
                    config.active_workspaces.append(workspace)

                subtask.workspace_name = workspace.name
                subtask.worktree_name = workspace.worktree_name

        else:  # Parallel tasks get their own workspaces
            # Create a unique workspace for this subtask
            workspace_name = f"task-{task.id}-{subtask.id}"

            # Create workspace with initial prompt
            workspace = create_workspace(
                project=project, name=workspace_name, config=config, initial_prompt=subtask_prompt
            )

            # Add workspace to global config
            if workspace not in config.active_workspaces:
                config.active_workspaces.append(workspace)

            subtask.workspace_name = workspace.name
            subtask.worktree_name = workspace.worktree_name

        # Update task plan file
        update_task_plan(task)

        return subtask

    except Exception as e:
        raise TaskError(f"Failed to execute subtask: {e}") from e


def complete_subtask(task: Task, subtask_id: str, config: GlobalConfig) -> Task:
    """Mark a subtask as completed.

    Args:
        task: The task
        subtask_id: The subtask ID to mark as completed
        config: The global configuration

    Returns:
        The updated task

    Raises:
        TaskError: If subtask completion fails
    """
    try:
        # Find the subtask
        subtask = None
        for st in task.subtasks:
            if st.id == subtask_id:
                subtask = st
                break

        if not subtask:
            raise TaskError(f"Subtask {subtask_id} not found")

        if subtask.status != "in_progress":
            raise TaskError(f"Subtask {subtask_id} is not in progress")

        # Update subtask status
        subtask.status = "completed"

        # For parallel tasks, we can destroy the workspace if it's not needed anymore
        if task.task_type == TaskType.PARALLEL:
            # Check if workspace should be destroyed
            workspace_name = subtask.workspace_name
            if workspace_name:
                # Find workspace
                workspace = None
                for ws in config.active_workspaces:
                    if ws.name == workspace_name and ws.project == task.project:
                        workspace = ws
                        break

                if workspace:
                    # TODO: In a real implementation, we'd ask if user wants to keep the workspace
                    # or push changes before destroying
                    pass

        # Check if all subtasks are completed
        all_completed = all(st.status == "completed" for st in task.subtasks)
        if all_completed:
            task.status = "completed"

        # Update task plan file
        update_task_plan(task)

        return task

    except Exception as e:
        raise TaskError(f"Failed to complete subtask: {e}") from e


def cancel_task(task: Task, config: GlobalConfig, force: bool = False) -> None:
    """Cancel a task and clean up resources.

    Args:
        task: The task to cancel
        config: The global configuration
        force: Whether to force cleanup of resources

    Raises:
        TaskError: If task cancellation fails
    """
    try:
        # Update task status
        task.status = "cancelled"

        # Clean up workspaces
        workspace_names = set()

        # Collect all workspaces associated with this task
        for subtask in task.subtasks:
            if subtask.workspace_name:
                workspace_names.add(subtask.workspace_name)

        # Find and destroy workspaces
        workspaces_to_remove = []
        for ws in config.active_workspaces:
            if ws.name in workspace_names and ws.project == task.project:
                try:
                    # TODO: In a real implementation, we'd ask if user wants to
                    # preserve changes before destroying
                    destroy_workspace(ws, config, force)
                    workspaces_to_remove.append(ws)
                except Exception as e:
                    # Log but continue with other workspaces
                    print(f"Warning: Failed to destroy workspace {ws.name}: {e}")

        # Remove destroyed workspaces from config
        for ws in workspaces_to_remove:
            if ws in config.active_workspaces:
                config.active_workspaces.remove(ws)

        # Remove task from global config
        if task in config.tasks:
            config.tasks.remove(task)

        # Update task plan file
        update_task_plan(task)

    except Exception as e:
        raise TaskError(f"Failed to cancel task: {e}") from e
