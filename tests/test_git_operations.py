"""Tests for Git operations functionality."""

import os
import subprocess
from pathlib import Path

import pytest

from workspace.core.git import create_worktree, list_worktrees, remove_worktree


class TestGitOperations:
    """Test class for Git operations."""

    @pytest.fixture(autouse=True)
    def setup_repo(self, temp_workspace_dir: Path) -> None:
        """Set up a test repository for each test."""
        # Change to the test repo directory
        os.chdir(temp_workspace_dir)

        # Save the repo path for tests
        self.repo_path = temp_workspace_dir
        self.worktree_path = temp_workspace_dir / "worktrees" / "test-worktree"
        self.worktree_path.parent.mkdir(exist_ok=True)

    def test_create_worktree(self):
        """Test creating a Git worktree."""
        # Create a worktree
        create_worktree(
            repo_path=self.repo_path, worktree_path=self.worktree_path, branch_name="test-branch"
        )

        # Verify worktree exists
        assert self.worktree_path.exists()

        # Verify branch exists
        result = subprocess.run(["git", "branch"], capture_output=True, text=True, check=True)
        assert "test-branch" in result.stdout

    def test_list_worktrees(self):
        """Test listing Git worktrees."""
        # Create a worktree first
        create_worktree(
            repo_path=self.repo_path,
            worktree_path=self.worktree_path,
            branch_name="test-branch-list",
        )

        # List worktrees
        worktrees = list_worktrees(self.repo_path)

        # Should have at least one worktree (the main one)
        assert len(worktrees) >= 1

        # Find our test worktree
        test_worktree = None
        for path, branch in worktrees:
            if "test-branch-list" in branch:
                test_worktree = path
                break

        # Verify our test worktree is in the list
        assert test_worktree is not None

    def test_remove_worktree(self):
        """Test removing a Git worktree."""
        # Create a worktree first
        create_worktree(
            repo_path=self.repo_path,
            worktree_path=self.worktree_path,
            branch_name="test-branch-remove",
        )

        # Verify it exists
        assert self.worktree_path.exists()

        # Remove the worktree
        remove_worktree(repo_path=self.repo_path, worktree_path=self.worktree_path)

        # Verify the directory no longer exists
        assert not self.worktree_path.exists()

        # Verify the branch still exists (removing worktree doesn't delete branch)
        result = subprocess.run(["git", "branch"], capture_output=True, text=True, check=True)
        assert "test-branch-remove" in result.stdout

    def test_create_worktree_from_base_branch(self):
        """Test creating a worktree from a specific base branch."""
        # Create a development branch
        subprocess.run(["git", "checkout", "-b", "development"], check=True)

        # Make a change on the development branch
        dev_file = self.repo_path / "dev.txt"
        with open(dev_file, "w") as f:
            f.write("Development branch content")

        subprocess.run(["git", "add", "dev.txt"], check=True)

        subprocess.run(["git", "commit", "-m", "Add development file"], check=True)

        # Create a feature branch from development
        feature_path = self.repo_path / "worktrees" / "feature-branch"
        create_worktree(
            repo_path=self.repo_path,
            worktree_path=feature_path,
            branch_name="feature",
            base_branch="development",
        )

        # Verify feature branch has development content
        assert (feature_path / "dev.txt").exists()

        # Clean up
        remove_worktree(self.repo_path, feature_path)
