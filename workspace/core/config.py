from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class Infrastructure(BaseModel):
    """Infrastructure configuration for a project"""

    start: str = Field(description="Command to start the infrastructure")
    stop: str = Field(description="Command to stop the infrastructure")
    test: Optional[str] = Field(None, description="Command to run tests")


class Agent(BaseModel):
    """Agent configuration for a project"""

    primary: Optional[str] = Field(None, description="Primary agent command")
    readonly: Optional[str] = Field(None, description="Read-only agent command")


class Project(BaseModel):
    """Project configuration"""

    name: str = Field(description="Project name")
    root_directory: Path = Field(description="Root directory of the project")
    infrastructure: Infrastructure = Field(description="Infrastructure configuration")
    agent: Optional[Agent] = Field(None, description="Agent configuration")


class ActiveWorkspace(BaseModel):
    """Active workspace configuration"""

    project: str = Field(description="Project name")
    name: str = Field(description="Workspace name")
    path: Path = Field(description="Path to the workspace")
    started: bool = Field(description="Whether the workspace is started")


class GlobalConfig(BaseModel):
    """Global configuration stored in ~/.workspace/config.toml"""

    projects: List[Project] = Field(default_factory=list, description="List of configured projects")
    active_workspaces: List[ActiveWorkspace] = Field(
        default_factory=list, description="List of active workspaces"
    )


class ProjectConfig(BaseModel):
    """Project-specific configuration stored in .workspace.toml"""

    name: str = Field(description="Project name")
    infrastructure: Dict[str, str] = Field(description="Infrastructure commands")
    agent: Dict[str, str] = Field(description="Agent commands")
