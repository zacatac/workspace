"""Tests for task management functionality."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from workspace.core.agent import analyze_task_with_agent
from workspace.core.config import (
    Agent,
    Infrastructure,
    ProjectConfig,
    SubTask,
    Task,
    TaskType,
)
from workspace.core.task import (
    complete_subtask,
    confirm_task_plan,
    create_task_plan,
    execute_subtask,
    get_ready_subtasks,
)


@pytest.fixture
def mock_task_id():
    """Create a mock task ID."""
    return "12345678"


@pytest.fixture
def example_task(mock_task_id, example_project_config):
    """Create a sample task for testing."""
    return Task(
        id=mock_task_id,
        name="Implement feature X",
        description="Add a new feature X to the project",
        project=example_project_config.name,
        task_type=TaskType.SEQUENTIAL,
        subtasks=[
            SubTask(
                id="st1",
                name="Create models",
                description="Create database models for feature X",
                dependencies=[],
                workspace_name=None,
                worktree_name=None,
                status="pending",
            ),
            SubTask(
                id="st2",
                name="Add API endpoints",
                description="Implement API endpoints for feature X",
                dependencies=["st1"],
                workspace_name=None,
                worktree_name=None,
                status="pending",
            ),
            SubTask(
                id="st3",
                name="Write tests",
                description="Create tests for feature X",
                dependencies=["st2"],
                workspace_name=None,
                worktree_name=None,
                status="pending",
            ),
        ],
        status="planning",
    )


class TestTaskManagement:
    """Test class for task management operations."""

    @patch("workspace.core.agent.subprocess.run")
    @patch("workspace.core.workspace.load_project_config")
    def test_analyze_task_with_agent(self, mock_load_config, mock_run, example_project_config):
        """Test analyzing a task with an agent."""
        # Mock loading project config
        mock_config = ProjectConfig(
            name="example",
            infrastructure=Infrastructure(
                start="echo 'Starting infrastructure'",
                stop="echo 'Stopping infrastructure'",
                test="echo 'Running tests'",
            ),
            agent=Agent(
                primary="echo 'Running primary agent'",
                readonly="echo 'Running readonly agent'",
            ),
        )
        mock_load_config.return_value = mock_config

        # Mock agent response
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = """
        Here's my analysis:

        {
          "name": "Implement Feature X",
          "task_type": "sequential",
          "subtasks": [
            {
              "id": "1",
              "name": "Create models",
              "description": "Create database models for feature X",
              "dependencies": []
            },
            {
              "id": "2",
              "name": "Add API endpoints",
              "description": "Implement API endpoints for feature X",
              "dependencies": ["1"]
            }
          ]
        }
        """
        mock_run.return_value = mock_process

        # Test analysis
        with patch("workspace.core.agent.generate_task_id", return_value="test-task-id"):
            task = analyze_task_with_agent(
                task_description="Implement feature X",
                project=example_project_config,
            )

        # Verify results
        assert task.name == "Implement Feature X"
        assert task.task_type == TaskType.SEQUENTIAL
        assert len(task.subtasks) == 2
        assert task.subtasks[0].name == "Create models"
        assert task.subtasks[1].dependencies == ["1"]

    @patch("workspace.core.agent.subprocess.run")
    @patch("workspace.core.workspace.load_project_config")
    def test_analyze_task_with_agent_process_management(
        self, mock_load_config, mock_run, example_project_config
    ):
        """Test analyzing a complex task with an agent and verify task structure."""
        # Mock loading project config
        mock_config = ProjectConfig(
            name="example",
            infrastructure=Infrastructure(
                start="echo 'Starting infrastructure'",
                stop="echo 'Stopping infrastructure'",
                test="echo 'Running tests'",
            ),
            agent=Agent(
                primary="echo 'Running primary agent'",
                readonly="echo 'Running readonly agent'",
            ),
        )
        mock_load_config.return_value = mock_config

        # Mock agent response with the provided example blob
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = """This is an example response. What follows is the actual JSON output. {
  "name": "Redesign process management for Claude tasks",
  "task_type": "sequential",
  "subtasks": [
    {
      "id": "1",
      "name": "Design task status tracking system",
      "description": "Create a data model and API for tracking Claude task status in tmux sessions. This includes defining the possible states (running, completed, failed, etc.) and the methods to update status.",
      "dependencies": []
    },
    {
      "id": "2",
      "name": "Implement tmux session process monitoring",
      "description": "Create functionality to check the status of Claude processes running in tmux sessions. This should include methods to determine if a Claude process is still running or has completed its execution.",
      "dependencies": ["1"]
    },
    {
      "id": "3",
      "name": "Enhance workspace state management",
      "description": "Update workspace.py to track and persist the state of Claude processes. This includes integrating process monitoring with the workspace management system.",
      "dependencies": ["2"]
    },
    {
      "id": "4",
      "name": "Add process status CLI commands",
      "description": "Create CLI commands to check the status of Claude tasks running in workspaces. This should allow users to list all tasks and their statuses.",
      "dependencies": ["3"]
    },
    {
      "id": "5",
      "name": "Implement auto-cleanup for completed tasks",
      "description": "Add functionality to automatically perform cleanup actions when a Claude task is detected as completed. This may include options to keep or destroy the workspace.",
      "dependencies": ["3", "4"]
    },
    {
      "id": "6",
      "name": "Add task notification system",
      "description": "Implement a system to notify users when Claude tasks complete. This could include terminal notifications or integration with system notification APIs.",
      "dependencies": ["3"]
    },
    {
      "id": "7",
      "name": "Write tests for process management",
      "description": "Create comprehensive tests for the new process management functionality, including unit tests and integration tests to verify proper status tracking and cleanup.",
      "dependencies": ["5", "6"]
    }
  ]
} And here is some useless cruft at the end"""
        mock_run.return_value = mock_process

        # Test analysis with fixed task ID for deterministic testing
        with patch("workspace.core.agent.generate_task_id", return_value="test-task-id"):
            task = analyze_task_with_agent(
                task_description="Redesign process management for Claude tasks",
                project=example_project_config,
            )

        # Verify task properties
        assert task.name == "Redesign process management for Claude tasks"
        assert task.task_type == TaskType.SEQUENTIAL
        assert task.project == example_project_config.name
        assert task.status == "planning"
        assert task.id == "test-task-id"

        # Verify subtasks
        assert len(task.subtasks) == 7

        # Verify first subtask
        assert task.subtasks[0].id == "1"
        assert task.subtasks[0].name == "Design task status tracking system"
        assert "data model and API for tracking Claude task status" in task.subtasks[0].description
        assert task.subtasks[0].dependencies == []
        assert task.subtasks[0].status == "pending"

        # Verify second subtask
        assert task.subtasks[1].id == "2"
        assert task.subtasks[1].name == "Implement tmux session process monitoring"
        assert "check the status of Claude processes" in task.subtasks[1].description
        assert task.subtasks[1].dependencies == ["1"]

        # Verify a subtask with multiple dependencies
        assert task.subtasks[4].id == "5"
        assert task.subtasks[4].name == "Implement auto-cleanup for completed tasks"
        assert task.subtasks[4].dependencies == ["3", "4"]

        # Verify the last subtask
        assert task.subtasks[6].id == "7"
        assert task.subtasks[6].name == "Write tests for process management"
        assert task.subtasks[6].dependencies == ["5", "6"]

    def test_create_task_plan(self, example_project_config):
        """Test creating a task plan."""
        # We need to mock the analyze_task_with_agent function at the module level
        with (
            patch("workspace.core.task.analyze_task_with_agent") as mock_analyze,
            patch("workspace.core.task.save_task_plan") as mock_save,
        ):
            # Mock agent analysis
            mock_task = Task(
                id="test-task-id",
                name="Test Task",
                description="Task description",
                project=example_project_config.name,
                task_type=TaskType.SEQUENTIAL,
                subtasks=[],
                status="planning",
            )
            mock_analyze.return_value = mock_task
            mock_save.return_value = Path("/mock/path.toml")

            # Create task plan
            task = create_task_plan(
                project=example_project_config,
                task_description="Test task",
            )

            # Verify results
            assert task.id == "test-task-id"
            assert task.name == "Test Task"
            assert task.status == "planning"
            mock_analyze.assert_called_once()
            mock_save.assert_called_once()

    @patch("workspace.core.task.load_task_plan")
    @patch("workspace.core.task.update_task_plan")
    def test_confirm_task_plan(self, mock_update, mock_load, example_task, global_config):
        """Test confirming a task plan."""
        # Mock loading the task
        mock_load.return_value = example_task

        # Confirm task plan
        task = confirm_task_plan("test-task-id", global_config)

        # Verify results
        assert task.status == "in_progress"
        assert task in global_config.tasks
        mock_update.assert_called_once()

    def test_get_ready_subtasks(self, example_task):
        """Test getting ready subtasks."""
        # Initially only the first subtask should be ready
        ready = get_ready_subtasks(example_task)
        assert len(ready) == 1
        assert ready[0].id == "st1"

        # Mark first subtask as completed
        example_task.subtasks[0].status = "completed"
        ready = get_ready_subtasks(example_task)
        assert len(ready) == 1
        assert ready[0].id == "st2"

        # Mark second subtask as completed
        example_task.subtasks[1].status = "completed"
        ready = get_ready_subtasks(example_task)
        assert len(ready) == 1
        assert ready[0].id == "st3"

    @patch("workspace.core.task.create_workspace")
    @patch("workspace.core.task.update_task_plan")
    def test_execute_subtask_sequential(
        self, mock_update, mock_create, example_task, global_config, example_project_config
    ):
        """Test executing a subtask in a sequential task."""
        # Add project to global config
        global_config.projects.append(example_project_config)

        # Mock workspace creation
        mock_workspace = MagicMock()
        mock_workspace.name = f"task-{example_task.id}"
        mock_workspace.worktree_name = "test-worktree"
        mock_workspace.path = Path("/mock/path")
        mock_create.return_value = mock_workspace

        # Execute subtask
        subtask = execute_subtask(example_task, "st1", global_config)

        # Verify results
        assert subtask.status == "in_progress"
        assert subtask.workspace_name == f"task-{example_task.id}"
        assert subtask.worktree_name == "test-worktree"
        mock_create.assert_called_once()
        mock_update.assert_called_once()

    @patch("workspace.core.task.update_task_plan")
    def test_complete_subtask(self, mock_update, example_task, global_config):
        """Test completing a subtask."""
        # Setup
        example_task.subtasks[0].status = "in_progress"
        example_task.subtasks[0].workspace_name = "test-workspace"

        # Complete subtask
        task = complete_subtask(example_task, "st1", global_config)

        # Verify results
        assert task.subtasks[0].status == "completed"
        mock_update.assert_called_once()

        # Test task completion when all subtasks are completed
        # Set all subtasks to in_progress first, then complete them
        for st in task.subtasks:
            st.status = "in_progress"

        # Complete all subtasks
        for st in task.subtasks:
            task = complete_subtask(task, st.id, global_config)

        # Verify task is completed
        assert task.status == "completed"
