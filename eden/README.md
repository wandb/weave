# Eden

## The Problem
Working with Model Control Protocol (MCP) servers today presents several challenges for developers and organizations:

1. **Fragmented Access**: Developers must manage connections to multiple MCP servers individually, each with their own authentication, configuration, and monitoring requirements.

2. **Deployment Complexity**: There's no standardized way to deploy and run MCP servers. Teams must choose between various approaches (remote servers, containers, local scripts) without clear guidance or tooling.

3. **Limited Discovery**: Finding reliable and secure MCP servers is difficult. There's no central place to discover, verify, and share MCP server implementations.

4. **Debugging Challenges**: When issues arise, developers lack proper tools to inspect, debug, and monitor MCP server behavior.

5. **Visibility Gaps**: Organizations struggle to maintain visibility into MCP server usage, performance, and errors across their infrastructure.

## Our Vision
Eden aims to be the unified platform for working with MCP servers. We envision a world where:

- Developers can seamlessly work with multiple MCP servers through a single interface
- Teams can easily deploy, manage, and monitor their MCP infrastructure
- Organizations can discover and verify reliable MCP servers
- Everyone has the tools they need to debug and optimize their MCP workflows

## System Overview

### Core Components

#### 1. Server Aggregator
The heart of Eden is a central server that unifies access to multiple MCP servers. Think of it as a smart reverse proxy that:
- Provides a single entry point to all your MCP servers
- Maintains isolated namespaces for each server's tools and resources
- Handles authentication and access control
- Enables human-in-the-loop approvals for sensitive operations
- Offers configurable rate limits and quotas

#### 2. Server Execution Framework
Eden supports multiple ways to run MCP servers through a unified configuration system:

##### Configuration Format
The core of Eden is a configuration specification that defines MCP servers. Each server entry contains:
- A unique ID
- A server definition specifying the type and configuration

Example configuration file (`eden.yaml`):
```yaml
servers:
  # Remote MCP server
  my-remote-server:
    type: remote
    url: https://api.example.com/mcp
    auth:
      type: bearer
      token: ${ENV_VAR_TOKEN}

  # Docker-based MCP server
  my-docker-server:
    type: docker
    image: my-mcp-server:latest
    port: 8000  # Optional, defaults to 8000
    env:
      API_KEY: ${ENV_VAR_API_KEY}

  # Script-based MCP server
  my-script-server:
    type: script
    path: ./my_server.py
    # Dependencies are managed by uv in the script itself

  # Local directory MCP server
  my-local-server:
    type: local
    path: ./my_mcp_project
```

Each server type has its own configuration requirements:

1. **Remote**
   - `url`: The URL of the MCP server
   - `auth`: Authentication configuration (optional)

2. **Docker**
   - `image`: Docker image to run
   - `port`: Port mapping (optional, defaults to 8000)
   - `env`: Environment variables (optional)

3. **Script**
   - `path`: Path to the Python script
   - Dependencies are managed by `uv` in the script itself

4. **Local Directory**
   - `path`: Path to the local MCP server project

##### Server Types
1. **Remote**
   - Connect to existing MCP servers
   - Configure connection details and authentication

2. **Docker**
   - Run MCP servers in containers
   - Standard port 8000 for MCP server exposure
   - Configurable port mapping
   - Container resource management

3. **Script**
   - Run Python scripts that implement MCP servers
   - Uses `uv` package manager for dependency management
   - Scripts must implement a standard MCP server using FastMCP:
     ```python
     from mcp.server.fastmcp import FastMCP
     
     mcp = FastMCP("My App")
     
     if __name__ == "__main__":
         mcp.run()
     ```
   - Dependencies specified using `uv` script format:
     ```python
     # /// script
     # dependencies = [
     #   "mcp-server",
     #   "other-dependencies",
     # ]
     # ///
     ```

4. **Local Directory**
   - Run MCP servers from local development directories
   - Useful for active development and testing

#### 3. Server Registry
A community hub for discovering and sharing MCP servers:
- Browse verified and community-tested servers
- Access documentation and usage examples
- Share your own server implementations
- Get notified of updates and security patches

#### 4. Development Environment
Tools designed for the developer workflow:
- Interactive playground for testing and experimentation
- Real-time debugging and inspection
- Performance monitoring and optimization
- Documentation generation and sharing

### How It All Works Together

1. **Getting Started**
   - Define your MCP servers in the Eden configuration
   - Choose the appropriate server type for each use case
   - Connect to the Eden aggregator

2. **Daily Development**
   - Use the unified interface to interact with all your servers
   - Debug issues with the inspector
   - Experiment with new ideas in the playground
   - Share your work with the community

3. **Production Operations**
   - Monitor server health and performance
   - Manage access and approvals
   - Track usage and optimize resources
   - Stay updated with security patches

## Key Features

### For Developers
- Single interface for all MCP servers
- Flexible deployment options
- Powerful debugging tools
- Community resources and examples

### For Teams
- Centralized access control
- Usage monitoring and quotas
- Approval workflows
- Documentation sharing

### For Organizations
- Security and compliance controls
- Performance monitoring
- Resource optimization
- Community engagement

## Success Looks Like
- Developers spend less time managing MCP infrastructure
- Teams can easily discover and use new MCP servers
- Organizations have better visibility and control
- The MCP ecosystem grows through community contributions

## Getting Started
[Coming soon: Installation and quickstart guide]

## Documentation
[Coming soon: Detailed documentation and examples]

## Community
[Coming soon: Community guidelines and contribution information]
