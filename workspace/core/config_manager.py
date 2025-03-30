import os
from pathlib import Path
from typing import Optional

import tomli
import tomli_w

from workspace.core.config import GlobalConfig, Project, ProjectConfig


class ConfigError(Exception):
    """Base exception for configuration operations."""

    pass


def get_config_dir() -> Path:
    """Get the workspace configuration directory."""
    config_dir = Path.home() / ".workspace"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def load_global_config() -> GlobalConfig:
    """Load the global configuration file.

    Returns:
        The global configuration

    Raises:
        ConfigError: If loading the configuration fails
    """
    config_file = get_config_dir() / "config.toml"

    if not config_file.exists():
        return GlobalConfig()

    try:
        with open(config_file, "rb") as f:
            data = tomli.load(f)
        return GlobalConfig.model_validate(data)

    except (OSError, tomli.TOMLDecodeError, ValueError) as e:
        raise ConfigError(f"Failed to load global configuration: {e}")


def save_global_config(config: GlobalConfig) -> None:
    """Save the global configuration file.

    Args:
        config: The configuration to save

    Raises:
        ConfigError: If saving the configuration fails
    """
    config_file = get_config_dir() / "config.toml"

    try:
        with open(config_file, "wb") as f:
            tomli_w.dump(config.model_dump(mode="json", exclude_none=True), f)

    except (OSError, TypeError) as e:
        raise ConfigError(f"Failed to save global configuration: {e}")


def load_project_config(project_dir: Path) -> Optional[ProjectConfig]:
    """Load a project's configuration file.

    Args:
        project_dir: The project directory to load configuration from

    Returns:
        The project configuration, or None if no configuration exists

    Raises:
        ConfigError: If loading the configuration fails
    """
    config_file = project_dir / ".workspace.toml"

    if not config_file.exists():
        return None

    try:
        with open(config_file, "rb") as f:
            data = tomli.load(f)
        return ProjectConfig.model_validate(data)

    except (OSError, tomli.TOMLDecodeError, ValueError) as e:
        raise ConfigError(f"Failed to load project configuration: {e}")


def save_project_config(config: ProjectConfig, project_dir: Path) -> None:
    """Save a project's configuration file.

    Args:
        config: The configuration to save
        project_dir: The project directory to save configuration to

    Raises:
        ConfigError: If saving the configuration fails
    """
    config_file = project_dir / ".workspace.toml"

    try:
        with open(config_file, "wb") as f:
            tomli_w.dump(config.model_dump(mode="json", exclude_none=True), f)

    except (OSError, TypeError) as e:
        raise ConfigError(f"Failed to save project configuration: {e}")


def find_project_root(start_dir: Optional[Path] = None) -> Optional[Path]:
    """Find the root directory of a project by looking for .workspace.toml.

    Args:
        start_dir: Directory to start searching from (defaults to current directory)

    Returns:
        The project root directory, or None if not found
    """
    current = start_dir or Path.cwd()

    while current != current.parent:
        if (current / ".workspace.toml").exists():
            return current
        current = current.parent

    return None
