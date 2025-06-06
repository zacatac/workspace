import json
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

import tomli
import tomli_w

from workspace.core.config import Project, SubTask, Task, TaskType
from workspace.core.workspace import load_project_config


class AgentError(Exception):
    """Base exception for agent operations."""

    pass


def get_task_plan_path(task_id: str) -> Path:
    """Get the path to the task plan file.

    Args:
        task_id: The task ID

    Returns:
        The path to the task plan file
    """
    config_dir = Path.home() / ".workspace" / "tasks"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / f"{task_id}.toml"


def generate_task_id() -> str:
    """Generate a unique task ID.

    Returns:
        A unique task ID
    """
    return str(uuid.uuid4())[:8]


def generate_subtask_id() -> str:
    """Generate a unique subtask ID.

    Returns:
        A unique subtask ID
    """
    return str(uuid.uuid4())[:8]


def analyze_task_with_agent(
    task_description: str, project: Project, agent_command: str | None = None
) -> Task:
    """Use an agent to analyze a task and break it into structured subtasks.

    Args:
        task_description: The user's description of the task
        project: The project for this task
        agent_command: Optional command to run the agent (defaults to project agent or Claude Code)

    Returns:
        A structured Task object with subtasks

    Raises:
        AgentError: If agent execution fails
    """
    try:
        # Load the project config to access agent configuration
        project_config = load_project_config(project)

        # Determine agent command to use
        cmd = None
        if agent_command:
            cmd = agent_command
        elif project_config.agent and project_config.agent.primary:
            cmd = project_config.agent.primary
        else:
            # Default to Claude Code if installed
            cmd = "claude"

        # Create prompt for the agent
        prompt = f"""
I need you to break down a development task into subtasks. This is a non-interactive request.
Please respond with a JSON object only, no conversation.

PROJECT: {project.name}

TASK DESCRIPTION:
{task_description}

Your job is to:
1. Determine if task should be SEQUENTIAL (all changes in one workspace) or PARALLEL
2. Break down the task into logical subtasks
3. Identify dependencies between subtasks (which subtasks depend on others)
4. Return a structured plan

For SEQUENTIAL tasks, work happens in a single worktree with changes building on each other.
For PARALLEL tasks, each subtask will have its own independent worktree.

IMPORTANT: You must return only a JSON object with the following structure, with no other text:
{{
  "name": "Short task name",
  "task_type": "sequential" or "parallel",
  "subtasks": [
    {{
      "id": "1",
      "name": "Short subtask name",
      "description": "Detailed description of what needs to be done",
      "dependencies": []
    }},
    {{
      "id": "2",
      "name": "Another subtask",
      "description": "Description",
      "dependencies": ["1"]  // This subtask depends on subtask with id "1"
    }}
  ]
}}
"""

        # Run the agent command with the initial prompt provided directly
        # For Claude Code we need to use --print for non-interactive mode
        # Adding --allowedTools Bash,GlobTool,GrepTool,View to ensure it has permissions to analyze
        if "claude" in cmd and "--print" not in cmd:
            cmd = f"{cmd} --print --allowedTools Bash,GlobTool,GrepTool,View,LS"
        result = subprocess.run(
            cmd,
            shell=True,
            input=prompt,
            text=True,
            capture_output=True,
        )

        if result.returncode != 0:
            raise AgentError(f"Agent execution failed: {result.stderr}")

        # Parse agent's response to find JSON
        response = result.stdout

        # Extract JSON from response (agent might include other text)
        # Claude Code will likely have conversation elements in the output
        start = response.find("{")
        end = response.rfind("}") + 1

        if start == -1 or end == 0:
            # If direct JSON extraction fails, try to find code blocks which may contain JSON
            code_block_start = response.find("```json")
            if code_block_start != -1:
                json_start = response.find("\n", code_block_start) + 1
                code_block_end = response.find("```", json_start)
                if code_block_end != -1:
                    json_str = response[json_start:code_block_end].strip()
                    agent_plan = json.loads(json_str)
                else:
                    raise AgentError("No valid JSON found in agent response")
            else:
                raise AgentError("No valid JSON found in agent response")
        else:
            json_str = response[start:end]
            agent_plan = json.loads(json_str)

        # Generate unique IDs for the task and subtasks if not provided
        task_id = generate_task_id()

        # Parse subtasks, ensuring each has a unique ID
        subtasks = []
        for st in agent_plan["subtasks"]:
            # Use provided ID or generate a new one
            st_id = st.get("id", generate_subtask_id())
            subtasks.append(
                SubTask(
                    id=st_id,
                    name=st["name"],
                    description=st["description"],
                    dependencies=st.get("dependencies", []),
                    workspace_name=None,
                    worktree_name=None,
                    status="pending",
                )
            )

        # Create the task
        task = Task(
            id=task_id,
            name=agent_plan["name"],
            description=task_description,
            project=project.name,
            task_type=TaskType(agent_plan["task_type"]),
            subtasks=subtasks,
            created_at=datetime.now(),
            status="planning",  # Initial status is planning until confirmed
        )

        return task

    except (subprocess.SubprocessError, json.JSONDecodeError, ValueError, KeyError) as e:
        raise AgentError(f"Error analyzing task with agent: {e}") from e


def save_task_plan(task: Task) -> Path:
    """Save the task plan to a TOML file for user review.

    Args:
        task: The task plan

    Returns:
        Path to the saved TOML file

    Raises:
        AgentError: If saving fails
    """
    try:
        # Convert to dictionary and exclude None values
        task_dict = task.model_dump(mode="json", exclude_none=True)

        # Save to TOML file
        path = get_task_plan_path(task.id)
        with open(path, "wb") as f:
            tomli_w.dump(task_dict, f)

        return path

    except (OSError, TypeError) as e:
        raise AgentError(f"Failed to save task plan: {e}") from e


def load_task_plan(task_id: str) -> Task:
    """Load a task plan from a TOML file.

    Args:
        task_id: The task ID

    Returns:
        The loaded task

    Raises:
        AgentError: If loading fails
    """
    try:
        path = get_task_plan_path(task_id)

        if not path.exists():
            raise AgentError(f"Task plan {task_id} not found")

        with open(path, "rb") as f:
            data = tomli.load(f)

        # Convert back to Task object
        return Task.model_validate(data)

    except (OSError, tomli.TOMLDecodeError, ValueError) as e:
        raise AgentError(f"Failed to load task plan: {e}") from e


def update_task_plan(task: Task) -> None:
    """Update a task plan file.

    Args:
        task: The updated task

    Raises:
        AgentError: If updating fails
    """
    try:
        # Save updated task
        save_task_plan(task)

    except Exception as e:
        raise AgentError(f"Failed to update task plan: {e}") from e
