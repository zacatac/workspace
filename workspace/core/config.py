import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class Infrastructure(BaseModel):
    """Infrastructure configuration for a project"""

    start: str = Field(description="Command to start the infrastructure")
    stop: str = Field(description="Command to stop the infrastructure")
    test: str | None = Field(None, description="Command to run tests")


class Agent(BaseModel):
    """Agent configuration for a project"""

    primary: str | None = Field(None, description="Primary agent command")
    readonly: str | None = Field(None, description="Read-only agent command")


class Project(BaseModel):
    """Project configuration in global config"""

    name: str = Field(description="Project name")
    root_directory: Path = Field(description="Root directory of the project")
    infrastructure: Infrastructure | None = Field(None, description="Infrastructure configuration")
    agent: Agent | None = Field(None, description="Agent configuration")


class ActiveWorkspace(BaseModel):
    """Active workspace configuration"""

    project: str = Field(description="Project name")
    name: str = Field(description="Workspace name")
    worktree_name: str = Field(description="Worktree name used for the directory and git branch")
    path: Path = Field(description="Path to the workspace")
    started: bool = Field(description="Whether the workspace is started")
    tmux_session: str | None = Field(None, description="Name of the associated tmux session")


class TaskType(str, Enum):
    """Task execution pattern"""

    SEQUENTIAL = "sequential"  # Changes stacked in one worktree
    PARALLEL = "parallel"  # Changes in independent worktrees


class SubTask(BaseModel):
    """A component of a larger task"""

    id: str = Field(description="Unique identifier for the subtask")
    name: str = Field(description="Short descriptive name")
    description: str = Field(description="Detailed description of what needs to be done")
    workspace_name: str | None = Field(None, description="Name of associated workspace if created")
    worktree_name: str | None = Field(None, description="Name of associated worktree if created")
    dependencies: list[str] = Field(
        default_factory=list, description="IDs of subtasks this depends on"
    )
    status: str = Field("pending", description="Current status (pending, in_progress, completed)")


class Task(BaseModel):
    """High-level task potentially spanning multiple workspaces"""

    id: str = Field(description="Unique identifier for the task")
    name: str = Field(description="Short descriptive name")
    description: str = Field(description="Detailed task description")
    project: str = Field(description="Project this task belongs to")
    task_type: TaskType = Field(description="Whether subtasks are sequential or parallel")
    subtasks: list[SubTask] = Field(default_factory=list, description="Component subtasks")
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
    status: str = Field("in_progress", description="Current overall status")


class GlobalConfig(BaseModel):
    """Global configuration stored in ~/.workspace/config.toml"""

    projects: list[Project] = Field(default_factory=list, description="List of configured projects")
    active_workspaces: list[ActiveWorkspace] = Field(
        default_factory=list, description="List of active workspaces"
    )
    tasks: list[Task] = Field(
        default_factory=list, description="List of active multi-workspace tasks"
    )


class ProjectConfig(BaseModel):
    """Project-specific configuration stored in .workspace.toml"""

    name: str = Field(description="Project name")
    infrastructure: Infrastructure = Field(description="Infrastructure configuration")
    agent: Agent | None = Field(None, description="Agent configuration")
