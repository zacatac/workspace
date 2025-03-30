from pathlib import Path

from git import Repo
from git.exc import GitCommandError


class GitError(Exception):
    """Base exception for Git operations."""

    pass


def create_worktree(
    repo_path: Path,
    worktree_path: Path,
    branch_name: str,
    base_branch: str | None = None,
) -> None:
    """Create a new Git worktree.

    Args:
        repo_path: Path to the Git repository
        worktree_path: Path where the worktree should be created
        branch_name: Name of the branch to create/checkout in the worktree
        base_branch: Optional base branch to create the new branch from

    Raises:
        GitError: If worktree creation fails
    """
    try:
        repo = Repo(repo_path)

        # Create new branch if it doesn't exist
        if branch_name not in repo.heads:
            base = repo.heads[base_branch] if base_branch else repo.head.ref
            new_branch = repo.create_head(branch_name, base)
        else:
            new_branch = repo.heads[branch_name]

        # Create worktree
        repo.git.worktree("add", str(worktree_path), new_branch.name)

    except GitCommandError as e:
        raise GitError(f"Failed to create worktree: {e}") from e


def remove_worktree(repo_path: Path, worktree_path: Path, force: bool = False) -> None:
    """Remove a Git worktree.

    Args:
        repo_path: Path to the Git repository
        worktree_path: Path to the worktree to remove
        force: Whether to force remove the worktree even if it has changes

    Raises:
        GitError: If worktree removal fails
    """
    try:
        repo = Repo(repo_path)
        args = ["remove"]
        if force:
            args.append("--force")
        args.append(str(worktree_path))
        repo.git.worktree(*args)

    except GitCommandError as e:
        raise GitError(f"Failed to remove worktree: {e}") from e


def list_worktrees(repo_path: Path) -> list[tuple[Path, str]]:
    """List all worktrees in a repository.

    Args:
        repo_path: Path to the Git repository

    Returns:
        List of tuples containing (worktree_path, branch_name)

    Raises:
        GitError: If listing worktrees fails
    """
    try:
        repo = Repo(repo_path)
        output = repo.git.worktree("list", "--porcelain")

        worktrees = []
        current_worktree = None
        current_branch = None

        for line in output.splitlines():
            if line.startswith("worktree "):
                if current_worktree and current_branch:
                    worktrees.append((Path(current_worktree), current_branch))
                current_worktree = line.split(" ", 1)[1]
                current_branch = None
            elif line.startswith("branch "):
                current_branch = line.split(" ", 1)[1].split("/")[-1]

        if current_worktree and current_branch:
            worktrees.append((Path(current_worktree), current_branch))

        return worktrees

    except GitCommandError as e:
        raise GitError(f"Failed to list worktrees: {e}") from e
