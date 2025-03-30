from pathlib import Path
from typing import Annotated, List, Optional, NoReturn

import typer
from rich.console import Console
from rich.table import Table

from workspace.core.config import GlobalConfig, Project
from workspace.core.workspace import (
    destroy_workspace,
    run_in_workspace,
    start_workspace,
    stop_workspace,
    WorkspaceError,
)

app = typer.Typer(
    help="A lightweight tool for managing concurrent development environments across projects",
    no_args_is_help=True,
)
console = Console()


def get_project(ctx: typer.Context, project_name: Optional[str] = None) -> Project:
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
    # TODO: Load configuration from ~/.workspace/config.toml
    ctx.obj = {"config": GlobalConfig()}


@app.command()
def create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the workspace to create")],
    project: Annotated[
        Optional[str], typer.Option(help="Project name to create workspace in")
    ] = None,
    branch: Annotated[Optional[str], typer.Option(help="Branch to base workspace on")] = None,
) -> None:
    """Create a new workspace for feature development."""
    project_config = get_project(ctx, project)
    console.print(f"Creating workspace [bold]{name}[/] in project [bold]{project_config.name}[/]")
    # TODO: Implement workspace creation


@app.command()
def list(ctx: typer.Context) -> None:
    """List all active workspaces."""
    config = ctx.obj["config"]

    table = Table(title="Active Workspaces")
    table.add_column("Project", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Path", style="blue")
    table.add_column("Status", style="yellow")

    for workspace in config.active_workspaces:
        status = "🟢 Running" if workspace.started else "⚫ Stopped"
        table.add_row(workspace.project, workspace.name, str(workspace.path), status)

    console.print(table)


@app.command()
def switch(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name of the workspace to switch to")],
) -> None:
    """Switch to an existing workspace."""
    config = ctx.obj["config"]
    for workspace in config.active_workspaces:
        if workspace.name == name:
            console.print(f"Switching to workspace [bold]{name}[/]")
            # TODO: Implement workspace switching
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
            except WorkspaceError as e:
                console.print(f"[red]Error:[/] {e}")
            return
    raise typer.BadParameter(f"Workspace {name} not found")


@app.command()
def run(
    ctx: typer.Context,
    workspace: Annotated[str, typer.Argument(help="Name of the workspace to run in")],
    command: Annotated[List[str], typer.Argument(help="Command to run in the workspace")],
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
            except WorkspaceError as e:
                console.print(f"[red]Error:[/] {e}")
            return
    raise typer.BadParameter(f"Workspace {name} not found")


if __name__ == "__main__":
    app()
