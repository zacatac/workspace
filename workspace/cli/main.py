import builtins
import os
import subprocess
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from workspace.core.agent import AgentError
from workspace.core.config import GlobalConfig, Project
from workspace.core.config_manager import load_global_config, save_global_config
from workspace.core.task import (
    TaskError,
    cancel_task,
    complete_subtask,
    confirm_task_plan,
    create_task_plan,
    execute_subtask,
    get_ready_subtasks,
    get_task_by_id,
)
from workspace.core.workspace import (
    WorkspaceError,
    attach_to_workspace_tmux,
    create_workspace,
    destroy_workspace,
    run_in_workspace,
    start_workspace,
    stop_workspace,
    switch_workspace,
)

app = typer.Typer(
    help="A lightweight tool for managing concurrent development environments across projects",
    no_args_is_help=True,
)
console = Console()


def get_project(ctx: typer.Context, project_name: str | None = None) -> Project:
    """Get the project configuration, either from the specified name or the current directory."""
    config: GlobalConfig = ctx.obj["config"]
    if project_name:
        for project in config.projects:
            if project.name == project_name:
                return project
        raise typer.BadParameter(f"Project {project_name} not found")

    # Try to find project based on current directory
    cwd = Path.cwd()
    for project in config.projects:
        if cwd.is_relative_to(project.root_directory):
            return project
    raise typer.BadParameter(
        "No project specified and current directory is not within a known project"
    )


@app.callback()
def callback(ctx: typer.Context) -> None:
    """Initialize the CLI context with global configuration."""
    # Load configuration from ~/.workspace/config.toml
    config = load_global_config()
    ctx.obj = {"config": config}


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the workspace to create")],
    project: Annotated[str | None, typer.Option(help="Project name to create workspace in")] = None,
    branch: Annotated[str | None, typer.Option(help="Branch to base workspace on")] = None,
) -> None:
    """Create a new workspace for feature development."""
    project_config = get_project(ctx, project)
    config = ctx.obj["config"]
    console.print(f"Creating workspace [bold]{name}[/] in project [bold]{project_config.name}[/]")

    try:
        workspace = create_workspace(
            project=project_config,
            name=name,
            branch=branch,
            config=config,
        )

        # Add workspace to active workspaces
        config.active_workspaces.append(workspace)
        save_config_if_not_testing(config)

        console.print(
            f"Workspace [bold]{name}[/] created successfully at [blue]{workspace.path}[/]"
        )
        console.print(f"Worktree name: [cyan]{workspace.worktree_name}[/]")

        if workspace.tmux_session:
            console.print(f"Tmux session: [magenta]{workspace.tmux_session}[/]")

        console.print(
            f"\nYou can now switch to this workspace with [cyan]workspace switch {name}[/]"
        )

        if workspace.tmux_session:
            console.print(f"Or attach to the tmux session with [cyan]workspace tmux {name}[/]")
    except WorkspaceError as e:
        console.print(f"[red]Error:[/] {e}")


@app.command()
def list(ctx: typer.Context) -> None:
    """List all active workspaces, projects, and tasks."""
    config = ctx.obj["config"]

    # Display projects
    console.print("\n[bold]Projects[/]")
    projects_table = Table()
    projects_table.add_column("Name", style="cyan")
    projects_table.add_column("Root Directory", style="blue")

    for project in config.projects:
        projects_table.add_row(project.name, str(project.root_directory))

    console.print(projects_table)

    # Display active workspaces
    console.print("\n[bold]Active Workspaces[/]")
    workspaces_table = Table()
    workspaces_table.add_column("Project", style="cyan")
    workspaces_table.add_column("Name", style="green")
    workspaces_table.add_column("Path", style="blue")
    workspaces_table.add_column("Status", style="yellow")
    workspaces_table.add_column("Tmux Session", style="magenta")

    for workspace in config.active_workspaces:
        status = "🟢 Running" if workspace.started else "⚫ Stopped"
        tmux_session = workspace.tmux_session or "None"
        workspaces_table.add_row(
            workspace.project, workspace.name, str(workspace.path), status, tmux_session
        )

    console.print(workspaces_table)

    # Display active tasks
    console.print("\n[bold]Active Tasks[/]")
    if not config.tasks:
        console.print("[yellow]No active tasks found.[/]")
    else:
        tasks_table = Table()
        tasks_table.add_column("ID", style="cyan")
        tasks_table.add_column("Name", style="green")
        tasks_table.add_column("Project", style="blue")
        tasks_table.add_column("Status", style="yellow")
        tasks_table.add_column("Subtasks", style="white")

        for task in config.tasks:
            completed = sum(1 for st in task.subtasks if st.status == "completed")
            status_str = f"{completed}/{len(task.subtasks)} completed"

            tasks_table.add_row(task.id, task.name, task.project, task.status, status_str)

        console.print(tasks_table)


@app.command()
def switch(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the workspace to switch to")],
    no_tmux: Annotated[
        bool, typer.Option("--no-tmux", help="Don't attach to tmux session if one exists")
    ] = False,
) -> None:
    """Switch to an existing workspace."""
    config = ctx.obj["config"]
    for workspace in config.active_workspaces:
        if workspace.name == name:
            console.print(f"Switching to workspace [bold]{name}[/]")
            try:
                # Note: This outputs a cd command that needs to be evaluated by the shell.
                # This won't actually change directories in the current process context
                switch_workspace(workspace, config, tmux_attach=not no_tmux)
                console.print("[bold yellow]Note:[/] To actually change directories, run:")
                console.print(f"[bold cyan]cd {workspace.path}[/]")

                if workspace.tmux_session and not no_tmux:
                    console.print("[bold yellow]Note:[/] To attach to tmux session, run:")
                    console.print(f"[bold cyan]tmux attach-session -t {workspace.tmux_session}[/]")
            except WorkspaceError as e:
                console.print(f"[red]Error:[/] {e}")
            return
    raise typer.BadParameter(f"Workspace {name} not found")


@app.command()
def tmux(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the workspace to attach to tmux session")],
) -> None:
    """Attach to a workspace's tmux session."""
    config = ctx.obj["config"]
    for workspace in config.active_workspaces:
        if workspace.name == name:
            try:
                if not workspace.tmux_session:
                    console.print(f"[yellow]Workspace [bold]{name}[/] has no tmux session[/]")
                    return

                console.print(f"Attaching to tmux session for workspace [bold]{name}[/]")

                # This will print the command that needs to be run to attach to the session
                attach_to_workspace_tmux(workspace)

                console.print("[bold yellow]Note:[/] To actually attach to the tmux session, run:")
                console.print(f"[bold cyan]tmux attach-session -t {workspace.tmux_session}[/]")
            except WorkspaceError as e:
                console.print(f"[red]Error:[/] {e}")
            return
    raise typer.BadParameter(f"Workspace {name} not found")


@app.command()
def start(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the workspace to start")],
) -> None:
    """Start a workspace's infrastructure."""
    config = ctx.obj["config"]
    for workspace in config.active_workspaces:
        if workspace.name == name:
            console.print(f"Starting workspace [bold]{name}[/]")
            try:
                start_workspace(workspace, config)
                console.print(f"Workspace [bold]{name}[/] started successfully")
                workspace.started = True
                save_global_config(config)
            except WorkspaceError as e:
                console.print(f"[red]Error:[/] {e}")
            return
    raise typer.BadParameter(f"Workspace {name} not found")


@app.command()
def run(
    ctx: typer.Context,
    workspace: Annotated[str, typer.Argument(help="Name of the workspace to run in")],
    command: Annotated[builtins.list[str], typer.Argument(help="Command to run in the workspace")],
) -> None:
    """Run a command in a specific workspace."""
    config = ctx.obj["config"]
    for ws in config.active_workspaces:
        if ws.name == workspace:
            console.print(
                f"Running command in workspace [bold]{workspace}[/]: [blue]{' '.join(command)}[/]"
            )
            try:
                result = run_in_workspace(ws, command)
                if result.returncode != 0:
                    console.print("[red]Command failed[/]")
                    return
                console.print("[green]Command completed successfully[/]")
            except WorkspaceError as e:
                console.print(f"[red]Error:[/] {e}")
            return
    raise typer.BadParameter(f"Workspace {workspace} not found")


@app.command()
def destroy(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the workspace to destroy")],
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Force destroy without confirmation")
    ] = False,
) -> None:
    """Destroy a workspace."""
    if not force:
        confirm = typer.confirm(f"Are you sure you want to destroy workspace {name}?")
        if not confirm:
            raise typer.Abort()

    config = ctx.obj["config"]
    for workspace in config.active_workspaces:
        if workspace.name == name:
            console.print(f"Destroying workspace [bold]{name}[/]")
            try:
                destroy_workspace(workspace, config, force)
                # Remove workspace from active workspaces list
                config.active_workspaces.remove(workspace)
                save_config_if_not_testing(config)
                console.print(f"Workspace [bold]{name}[/] destroyed successfully")
            except WorkspaceError as e:
                console.print(f"[red]Error:[/] {e}")
            return
    raise typer.BadParameter(f"Workspace {name} not found")


@app.command()
def stop(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the workspace to stop")],
) -> None:
    """Stop a workspace's infrastructure."""
    config = ctx.obj["config"]
    for workspace in config.active_workspaces:
        if workspace.name == name:
            console.print(f"Stopping workspace [bold]{name}[/]")
            try:
                stop_workspace(workspace, config)
                console.print(f"Workspace [bold]{name}[/] stopped successfully")
                workspace.started = False
                save_global_config(config)
            except WorkspaceError as e:
                console.print(f"[red]Error:[/] {e}")
            return
    raise typer.BadParameter(f"Workspace {name} not found")


# Task management commands
task_app = typer.Typer(help="Manage multi-workspace tasks with agent assistance")
app.add_typer(task_app, name="task")


@task_app.command("create")
def task_create(
    ctx: typer.Context,
    description: Annotated[str, typer.Argument(help="Description of the task")],
    project: Annotated[str | None, typer.Option(help="Project name for the task")] = None,
    agent: Annotated[str | None, typer.Option(help="Agent command to use for analysis")] = None,
) -> None:
    """Create a new task plan using agent analysis."""
    try:
        # Get project
        project_config = get_project(ctx, project)

        # Use agent to analyze task
        console.print(f"Analyzing task for project [bold]{project_config.name}[/]...")
        task = create_task_plan(
            project=project_config, task_description=description, agent_command=agent
        )

        # Show task plan summary
        console.print(f"\n[bold green]Task Plan Created: {task.id}[/]")
        console.print(f"[bold]{task.name}[/]")
        console.print(f"Type: [cyan]{task.task_type.value}[/]")

        # Show subtasks
        table = Table(title="Subtasks")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Description", style="white")
        table.add_column("Dependencies", style="yellow")

        for subtask in task.subtasks:
            deps = ", ".join(subtask.dependencies) if subtask.dependencies else "None"
            table.add_row(
                subtask.id,
                subtask.name,
                subtask.description[:50] + ("..." if len(subtask.description) > 50 else ""),
                deps,
            )

        console.print(table)

        # Instructions for next steps
        console.print("\n[bold]Next Steps:[/]")
        console.print(f"1. Review the task plan at [cyan]~/.workspace/tasks/{task.id}.toml[/]")
        console.print("2. Edit the plan if needed")
        console.print(f"3. Confirm the plan with [cyan]workspace task confirm {task.id}[/]")

    except (TaskError, AgentError) as e:
        console.print(f"[red]Error:[/] {e}")


@task_app.command("confirm")
def task_confirm(
    ctx: typer.Context,
    task_id: Annotated[str, typer.Argument(help="ID of the task to confirm")],
) -> None:
    """Confirm a task plan and make it active."""
    try:
        config = ctx.obj["config"]

        # Confirm task plan
        task = confirm_task_plan(task_id, config)
        save_config_if_not_testing(config)

        console.print(f"[bold green]Task Confirmed: {task.id}[/]")
        console.print(f"[bold]{task.name}[/] is now active")

        # Show ready subtasks
        ready = get_ready_subtasks(task)
        if ready:
            console.print("\n[bold]Ready to work on:[/]")
            for subtask in ready:
                console.print(f"• [cyan]{subtask.id}[/]: {subtask.name}")
            console.print(
                f"\nStart working with [cyan]workspace task start {task.id} <subtask_id>[/]"
            )
        else:
            console.print("\n[yellow]No subtasks are ready to work on yet.[/]")

    except TaskError as e:
        console.print(f"[red]Error:[/] {e}")


@task_app.command("list")
def task_list(ctx: typer.Context) -> None:
    """List all active tasks."""
    config = ctx.obj["config"]

    if not config.tasks:
        console.print("[yellow]No active tasks found.[/]")
        return

    table = Table(title="Active Tasks")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Project", style="blue")
    table.add_column("Type", style="magenta")
    table.add_column("Status", style="yellow")
    table.add_column("Subtasks", style="white")

    for task in config.tasks:
        completed = sum(1 for st in task.subtasks if st.status == "completed")
        status_str = f"{completed}/{len(task.subtasks)} completed"

        table.add_row(
            task.id, task.name, task.project, task.task_type.value, task.status, status_str
        )

    console.print(table)


@task_app.command("show")
def task_show(
    ctx: typer.Context,
    task_id: Annotated[str, typer.Argument(help="ID of the task to show")],
) -> None:
    """Show details of a task."""
    config = ctx.obj["config"]

    # Find task
    task = get_task_by_id(task_id, config)
    if not task:
        console.print(f"[red]Error:[/] Task {task_id} not found")
        return

    # Display task details
    console.print(f"[bold green]Task: {task.id}[/]")
    console.print(f"[bold]{task.name}[/]")
    console.print(f"Project: [blue]{task.project}[/]")
    console.print(f"Type: [magenta]{task.task_type.value}[/]")
    console.print(f"Status: [yellow]{task.status}[/]")
    console.print(f"Created: {task.created_at.strftime('%Y-%m-%d %H:%M')}")

    console.print("\n[bold]Description:[/]")
    console.print(Panel(task.description))

    # Show subtasks
    table = Table(title="Subtasks")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Workspace", style="blue")
    table.add_column("Dependencies", style="magenta")

    for subtask in task.subtasks:
        deps = ", ".join(subtask.dependencies) if subtask.dependencies else "None"
        workspace = subtask.workspace_name or "Not created"

        # Determine status color
        status_color = {"pending": "white", "in_progress": "yellow", "completed": "green"}.get(
            subtask.status, "white"
        )

        table.add_row(
            subtask.id, subtask.name, f"[{status_color}]{subtask.status}[/]", workspace, deps
        )

    console.print(table)

    # Show ready subtasks
    ready = get_ready_subtasks(task)
    if ready:
        console.print("\n[bold]Ready to work on:[/]")
        for subtask in ready:
            console.print(f"• [cyan]{subtask.id}[/]: {subtask.name}")


@task_app.command("start")
def task_start(
    ctx: typer.Context,
    task_id: Annotated[str, typer.Argument(help="ID of the task")],
    subtask_id: Annotated[str, typer.Argument(help="ID of the subtask to start working on")],
) -> None:
    """Start working on a subtask."""
    try:
        config = ctx.obj["config"]

        # Find task
        task = get_task_by_id(task_id, config)
        if not task:
            console.print(f"[red]Error:[/] Task {task_id} not found")
            return

        # Execute subtask
        subtask = execute_subtask(task, subtask_id, config)
        save_config_if_not_testing(config)

        console.print(f"[bold green]Started work on subtask: {subtask.id}[/]")
        console.print(f"[bold]{subtask.name}[/]")

        if subtask.workspace_name:
            console.print(f"\nWorkspace: [blue]{subtask.workspace_name}[/]")
            console.print(f"Worktree: [blue]{subtask.worktree_name}[/]")

            # Find workspace path
            workspace_path = None
            for ws in config.active_workspaces:
                if ws.name == subtask.workspace_name:
                    workspace_path = ws.path
                    break

            if workspace_path:
                console.print(f"Path: [green]{workspace_path}[/]")

        console.print("\n[bold]Description:[/]")
        console.print(Panel(subtask.description))

        console.print("\n[bold]When finished:[/]")
        console.print(f"Run [cyan]workspace task complete {task_id} {subtask_id}[/]")

    except TaskError as e:
        console.print(f"[red]Error:[/] {e}")


@task_app.command("complete")
def task_complete(
    ctx: typer.Context,
    task_id: Annotated[str, typer.Argument(help="ID of the task")],
    subtask_id: Annotated[str, typer.Argument(help="ID of the subtask to mark as completed")],
) -> None:
    """Mark a subtask as completed."""
    try:
        config = ctx.obj["config"]

        # Find task
        task = get_task_by_id(task_id, config)
        if not task:
            console.print(f"[red]Error:[/] Task {task_id} not found")
            return

        # Mark subtask as completed
        task = complete_subtask(task, subtask_id, config)
        save_config_if_not_testing(config)

        console.print(f"[bold green]Completed subtask: {subtask_id}[/]")

        # Check if all subtasks are completed
        if task.status == "completed":
            console.print(f"[bold green]Task {task_id} is now complete![/]")
        else:
            # Show ready subtasks
            ready = get_ready_subtasks(task)
            if ready:
                console.print("\n[bold]Next up:[/]")
                for subtask in ready:
                    console.print(f"• [cyan]{subtask.id}[/]: {subtask.name}")
                console.print(
                    f"\nStart working with [cyan]workspace task start {task_id} <subtask_id>[/]"
                )
            else:
                console.print("\n[yellow]No more subtasks are ready to work on yet.[/]")

    except TaskError as e:
        console.print(f"[red]Error:[/] {e}")


@task_app.command("cancel")
def task_cancel(
    ctx: typer.Context,
    task_id: Annotated[str, typer.Argument(help="ID of the task to cancel")],
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Force cancel without confirmation")
    ] = False,
) -> None:
    """Cancel a task and clean up its resources."""
    try:
        config = ctx.obj["config"]

        # Find task
        task = get_task_by_id(task_id, config)
        if not task:
            console.print(f"[red]Error:[/] Task {task_id} not found")
            return

        # Confirm cancellation
        if not force:
            confirm = typer.confirm(f"Are you sure you want to cancel task {task_id}?")
            if not confirm:
                raise typer.Abort()

        # Cancel task
        cancel_task(task, config, force)
        save_config_if_not_testing(config)

        console.print(f"[bold yellow]Task {task_id} has been cancelled[/]")

    except TaskError as e:
        console.print(f"[red]Error:[/] {e}")


@task_app.command("edit")
def task_edit(
    ctx: typer.Context,
    task_id: Annotated[str, typer.Argument(help="ID of the task to edit")],
) -> None:
    """Edit a task plan in your default editor."""
    try:
        # Get path to task plan
        from workspace.core.agent import get_task_plan_path

        plan_path = get_task_plan_path(task_id)

        if not plan_path.exists():
            console.print(f"[red]Error:[/] Task plan {task_id} not found")
            return

        # Open plan in editor
        editor = os.environ.get("EDITOR", "vim")
        subprocess.run([editor, plan_path])

        console.print(f"[green]Task plan {task_id} updated[/]")
        console.print(f"Run [cyan]workspace task confirm {task_id}[/] to apply changes")

    except Exception as e:
        console.print(f"[red]Error:[/] {e}")


def save_config_if_not_testing(config: GlobalConfig) -> None:
    """Save the global configuration if not in test mode.

    This helps prevent tests from overwriting the user's actual config file.
    """
    if os.environ.get("WORKSPACE_TEST_MODE") != "1":
        save_global_config(config)


if __name__ == "__main__":
    app()
