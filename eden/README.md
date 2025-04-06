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

## System Architecture

### Core API Layer
Eden is built with a core API layer that provides programmatic access to all functionality:
- Server management and configuration
- Tool execution and approval flows
- Session management
- Monitoring and telemetry

### Interfaces

#### Command Line Interface
The primary interface for Eden is the `eden` CLI tool, which serves two main purposes:

1. **Aggregator Service Management**
   - Start/stop the Eden aggregator service
   - Load and validate configuration files
   - Manage server and vendor connections
   - Handle service logs and monitoring

2. **Local Development Environment**
   - Launch the local GUI interface (automatically starts aggregator if needed)
   - Access the playground and other development tools
   - Manage local configurations
   - View logs and debug information

Example usage:
```bash
# Start the aggregator service with a config file
eden serve --config eden.yaml

# Launch the local GUI (automatically starts aggregator if needed)
eden gui

# Other common commands
eden status      # Check aggregator status
eden logs        # View service logs
eden config      # Validate/edit configuration
```

Configuration files:
- Default location: `~/.eden/config.yaml`
- Can be specified at startup with `--config`
- Configuration cannot be changed while the service is running
- Changes require restarting the service

#### Python Library
A Python library designed primarily as an onboarding tool for new users:
- Provides in-process alternatives to the standalone `eden` service and GUI
- Shares the same configuration file (`~/.eden/config.yaml`) as the standalone service
- Creates and manages local configuration automatically if none exists
- Spins up a local UI for development and testing
- Perfect for quick experiments and learning
- Not intended for production use (users should migrate to standalone service)

Example usage:
```python
import eden

# Start Eden in-process with automatic config and UI
# Uses ~/.eden/config.yaml if it exists, creates it if it doesn't
server_params = eden.start()

# Connect to the in-process server
async with sse_client(server_params) as (read, write):
    async with ClientSession(
        read, write, sampling_callback=handle_sampling_message
    ) as session:
        # Use the session as a normal MCP client
        ...
```

This approach allows users to quickly get started with Eden without understanding the full architecture, while naturally guiding them toward the more robust standalone service as they become more familiar with the system. The shared configuration ensures a smooth transition between in-process and standalone usage.

Note: Process management between in-process and standalone services (e.g., preventing both from running simultaneously) is a future consideration and not part of the MVP scope.

#### Graphical User Interface
A modern web-based interface that runs locally and includes multiple specialized views. The GUI is launched through the `eden` CLI tool and provides a complete development environment. When launched, it automatically starts a local aggregator service if one isn't already running, using the default configuration file (`~/.eden/config.yaml`).

The GUI provides seamless access to all Eden functionality while managing the underlying aggregator service transparently. Note that configuration changes require restarting the aggregator service.

##### Configuration View
- Server configuration management
- Tool settings and permissions
- Environment setup
- Authentication management

##### Playground View
A modern chat interface that serves as the canonical example of an MCP client:
- Implements full MCP client specification
- Uses MCP sampling for LLM interactions
- Demonstrates best practices for MCP client implementation
- Features:
  - Chat interface with LLM integration via MCP sampling
  - Tool execution and testing
  - Session management
  - Configuration sharing
  - Resource access and management
  - Prompt template handling
  - Smart LLM preference handling:
    - Respects server model preferences when possible
    - Falls back to playground's active LLM vendor when needed
    - Maintains session consistency

The playground's implementation serves as a reference for developers building their own MCP clients, showcasing proper protocol usage and integration patterns.

##### Inspector View
- Real-time monitoring
- Debug information
- Performance metrics
- Error tracking

##### Approver View
- Tool request management
- Approval workflows
- Request history
- Audit logs

## System Overview

### Core Components

#### 1. Server Aggregator
The heart of Eden is a central server that unifies access to multiple MCP servers and LLM vendors. It is itself a fully conformant MCP server that implements the complete MCP specification:
- Implements all MCP primitives (Tools, Resources, Prompts)
- Supports all MCP features (Completions, Sampling, etc.)
- Uses JSON-RPC message format and transport layer
- Maintains direct connections to all configured MCP servers and LLM vendors
- Clients only need a single connection to the Eden aggregator
- Acts as a reverse proxy for multiple MCP servers
- Maintains isolated namespaces for each server's tools and resources (using server IDs as namespace prefixes)
- Handles authentication and access control
- Enables human-in-the-loop approvals for sensitive operations
- Offers configurable rate limits and quotas

The aggregator manages all external connections:
- Maintains direct connections to all configured MCP servers
- Maintains direct connections to all configured LLM vendors
- Handles all routing between clients and servers/vendors
- Manages authentication for all connections
- Provides unified approval interface for both tool and sampling requests

This design means that any MCP client can connect to Eden as if it were a standard MCP server, while Eden handles the complexity of routing requests to the appropriate downstream servers and vendors. All MCP features are properly namespaced and managed through the aggregator.

#### 2. Server Execution Framework
Eden supports multiple ways to run MCP servers through a unified configuration system:

##### Configuration Format
The core of Eden is a configuration specification that defines MCP servers and LLM vendors. The configuration format is defined in `spec.ts` using TypeScript types. This provides a clear specification that can be translated to various formats (JSON, TOML, etc.).

Key aspects of the configuration:
- Each server has a unique ID
- Server types (Remote, Docker, Script, Local) have specific configuration requirements
- Tool settings control access and approval requirements for each tool
- Default port 8000 for Docker-based MCP servers
- Environment variable support for sensitive configuration
- LLM vendor configurations with vendor-specific settings and authentication
- Support for vendor-specific approval requirements

For the complete specification and examples, see `spec.ts`.

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
A community hub for discovering and sharing MCP servers. While the registry implementation is beyond MVP scope, it's an important part of the Eden ecosystem vision:
- Enables discovery of community-verified MCP servers
- Provides a trusted source for server implementations
- Facilitates sharing of best practices and patterns
- Creates a foundation for the MCP server ecosystem

The registry will integrate with Eden's configuration system, allowing users to easily import and use servers from the registry in their own Eden instances.

#### 4. Development Environment
Tools designed for the developer workflow, focusing on a streamlined playground experience:

##### Playground
A modern chat interface that leverages existing open-source solutions while adding MCP-specific capabilities:
- Support for various LLM vendors (from local Ollama to remote OpenAI)
- Named, preconfigured model settings (system prompts, parameters)
- Standard chat interface for model interaction
- Integration with configured MCP servers for tool access
- Session management and history
- Tool approval interface for managing tool access requests

The playground's key differentiator is its seamless integration with MCP servers, allowing developers to:
- Test MCP server tools directly in chat sessions
- Debug server interactions in real-time
- Experiment with different tool configurations
- Share working configurations with team members
- Manage tool access approvals through a dedicated interface

All tool calls are automatically routed through Eden's aggregator, making the playground the first client of the aggregator system.

##### Tool Approval Interface
A dedicated interface for managing tool access requests, showing approvers:
- Tool details (name, arguments, expected impact)
- Chat context (recent messages, conversation history)
- Request metadata (requesting user, timestamp, server ID)
- Previous approval history for similar requests
- Quick actions (approve, deny, request more information)

The interface is designed to give approvers full context for making informed decisions about tool access.

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

## References

### Model Control Protocol (MCP)
- [MCP Specification](https://github.com/wandb/mcp) - The core protocol that Eden implements and extends
- [MCP Python Client](https://github.com/wandb/mcp-python) - Reference implementation of MCP client
- [MCP Server](https://github.com/wandb/mcp-server) - Reference implementation of MCP server

### Key Design Decisions

#### Architecture
1. **Single Connection Point**
   - Clients only need to connect to the Eden aggregator
   - Aggregator maintains all connections to MCP servers and LLM vendors
   - Aggregator is a fully conformant MCP server

2. **Configuration Management**
   - Configuration defined in TypeScript types (`spec.ts`)
   - Default config location: `~/.eden/config.yaml`
   - Config cannot be changed while service is running
   - Changes require service restart

3. **Service Management**
   - Primary interface is the `eden` CLI tool
   - GUI automatically starts aggregator if needed
   - Service state is managed transparently

4. **LLM Integration**
   - Aggregator maintains direct connections to LLM vendors
   - Vendors configured in the same config file as servers
   - Support for vendor-specific approval requirements

5. **Tool Access Control**
   - Per-tool settings (ALLOWED, DISALLOWED, NEEDS_APPROVAL)
   - Server-level defaults
   - Human-in-the-loop approval interface

#### Implementation Priorities
1. Core aggregator functionality
2. Configuration system
3. Server execution framework
4. Development environment (CLI + GUI)
5. Community features (registry, etc.)

## Outstanding Topics

### MVP Implementation
1. **Core Aggregator Development**
   - Basic MCP server implementation
   - Server connection management
   - Simple error handling
   - Basic monitoring

2. **Configuration System**
   - YAML configuration parser
   - Configuration validation
   - Default configuration generation

3. **CLI Tool**
   - Service management commands
   - Configuration management
   - Basic monitoring commands

4. **GUI Development**
   - Playground implementation
   - Basic configuration UI
   - Tool approval interface

### Future Considerations
1. **Advanced Features**
   - Request queuing and retries
   - Complex error handling
   - Process management between in-process/standalone
   - Server registry implementation

2. **Production Features**
   - High availability
   - Load balancing
   - Advanced monitoring
   - Complex authentication

3. **Community Features**
   - Server registry
   - Community guidelines
   - Contribution process
   - Documentation

4. **Integration Features**
   - CI/CD integration
   - Cloud provider integration
   - Advanced deployment options
   - Monitoring integrations

Note: Many topics from the original list have been addressed in our MVP scope or moved to future considerations. The focus is now on implementing the core functionality needed to validate the product vision.

## MVP Scope

### Goals
The MVP aims to validate the core value proposition: making it easier for ML Engineers to work with MCP servers. Success means:
- ML Engineers can quickly start using multiple MCP servers
- Basic tool access control is in place
- Configuration is simple and clear
- Development experience is smooth

### Scope

#### In Scope
1. **Core Aggregator**
   - Basic MCP server implementation
   - Server connection management
   - Simple tool access control
   - LLM vendor integration

2. **Configuration**
   - TypeScript specification
   - YAML configuration files
   - Basic validation

3. **Interfaces**
   - CLI tool for service management
   - Simple GUI with playground
   - Basic Python library for onboarding

4. **Server Types**
   - Remote server connections
   - Docker server execution
   - Script server execution
   - Local directory server

#### Out of Scope
1. **Advanced Features**
   - Request queuing and retries
   - Complex error handling
   - Process management between in-process/standalone
   - Server registry implementation

2. **Production Features**
   - High availability
   - Load balancing
   - Advanced monitoring
   - Complex authentication

### Development Priorities
1. Core aggregator implementation
2. Basic configuration system
3. CLI tool
4. Simple GUI with playground
5. Python library for onboarding

### Success Criteria
- ML Engineers can connect to multiple MCP servers through a single interface
- Basic tool access control is working
- Configuration is understandable and maintainable
- Development experience is smooth and intuitive

## Getting Started
[Coming soon: Installation and quickstart guide]

## Documentation
[Coming soon: Detailed documentation and examples]

## Community
[Coming soon: Community guidelines and contribution information]
