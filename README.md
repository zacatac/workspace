# Workspace

> A lightweight tool for managing concurrent development environments across projects

## Background

Modern development often requires working on multiple features simultaneously, each with their own infrastructure dependencies, tests, and environment configurations. Constantly switching between branches, restarting services, and reconfiguring environments can be time-consuming and error-prone.

Workspace solves this by leveraging Git worktrees to create isolated development environments for each feature, while providing a simple interface to manage infrastructure, testing, and agent access across these environments.

## Installation

You can install Workspace using uv:

```bash
uv pip install -e .
```

## Usage

After installation, you can run the tool in several ways:

```bash
# Direct command (after installation)
workspace [command] [options]

# Using uv
uv run workspace [command] [options]

# Using the module directly
uv run -m workspace.cli.main [command] [options]
```

## Approach

Workspace uses a minimal, non-opinionated approach:

1. **Git Worktrees as a Foundation**: We use Git worktrees to create isolated file system views of your repository, prefixed with the project name.

2. **Container Flexibility**: Workspace assumes you're using Docker, OrbStack, or similar container systems, but doesn't enforce specific implementations. You define start/stop commands for your development environment.

3. **Two-Tier Configuration**:
   - Global configuration in your home directory tracks active workspaces and manages resources
   - Project-specific configuration defines how to spawn and configure workspaces

4. **Agent Integration**: Each workspace can have a dedicated agent with write access, while supporting shared read-only agents for research or analysis.

5. **CLI First, UI Ready**: Workspace is primarily accessed through a CLI but is designed with future UI integration in mind.

## Key Concepts

- **Project**: A Git repository (identified by name or directory location) that serves as the root for all related workspaces
- **Workspace**: An isolated development environment associated with a specific project, with its own Git worktree, infrastructure, and agents
- **Agents**: Automated processes with different permission levels that operate within workspaces

## Getting Started

```
# Create a new workspace for feature X in current project
workspace create feature-x

# Create a new workspace for feature X in a specific project
workspace create --project my-app feature-x

# List all active workspaces
workspace list

# Switch to an existing workspace
workspace switch feature-x

# Run a command in a specific workspace
workspace run feature-x [command-to-run]
For example: workspace run feature-x npm test

# Destroy a workspace when you're done
workspace destroy feature-x
```

## Configuration

### Global Configuration

Located in `~/.workspace/config.toml`:

```toml
# Projects configuration
[[projects]]
name = "my-app"
root_directory = "/path/to/my-app"

[[projects]]
name = "my-api"
root_directory = "/path/to/my-api"

# Active workspaces configuration
[[active_workspaces]]
project = "my-app"
name = "feature-x"
path = "/path/to/my-app/worktrees/my-app-feature-x"
started = true

[[active_workspaces]]
project = "my-api"
name = "bugfix-y"
path = "/path/to/my-api/worktrees/my-api-bugfix-y"
started = false
```

### Project Configuration

Located in `.workspace.toml` at your project root:

```toml
name = "my-app"

[infrastructure]
start = "docker-compose up -d"
stop = "docker-compose down"
test = "npm test"

[agent]
primary = "node scripts/agent.js"
readonly = "node scripts/readonly-agent.js"
```

## Planned Features

- Resource conflict detection and resolution
- Persistent workspace state (stashing changes when switching)
- Integration with popular CI systems
- Web UI for workspace management

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

[MIT](LICENSE)
