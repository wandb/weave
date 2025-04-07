# Eden

## Overview
Eden is a unified platform for working with Model Control Protocol (MCP) servers. It provides a single interface for connecting to multiple MCP servers, managing LLM vendors, and developing MCP-based applications.

### What is MCP?
The Model Control Protocol (MCP) is a standard for interacting with AI models and tools. It defines:
- Tools: Functions that models can call
- Resources: Data that models can access
- Prompts: Templates for model interactions
- Sampling: Standardized model inference

## The Problem
Working with MCP servers today presents several challenges for developers and organizations:

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

## MVP Scope

### Goals
The MVP aims to validate the core value proposition: making it easier for ML Engineers to work with MCP servers. Success means:
- ML Engineers can quickly start using multiple MCP servers
- Basic tool access control is in place
- Configuration is simple and clear
- Development experience is smooth

### Scope

#### In Scope
1. **Core Server**
   - Basic MCP server implementation
   - Server connection management
   - Simple tool access control
   - LLM vendor integration
   - Built-in UI for configuration, playground, and debugging

2. **Configuration**
   - JSON configuration file (`eden.json`)
   - TypeScript specification for type safety
   - Basic validation

3. **Command Line Interface**
   - `eden up` for starting the server
   - Utility commands for config management
   - Simple monitoring commands

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
1. Core server implementation
2. Configuration system
3. CLI tool
4. Built-in UI
5. Server type implementations

### Success Criteria
- ML Engineers can connect to multiple MCP servers through a single interface
- Basic tool access control is working
- Configuration is understandable and maintainable
- Development experience is smooth and intuitive

## System Architecture

### Core Components

#### 1. Eden Server
The heart of Eden is a stateless MCP server that unifies access to multiple MCP servers and LLM vendors. It is itself a fully conformant MCP server that implements the complete MCP specification:
- Implements all MCP primitives (Tools, Resources, Prompts)
- Supports all MCP features (Completions, Sampling, etc.)
- Uses JSON-RPC message format and transport layer
- Maintains direct connections to all configured MCP servers and LLM vendors
- Clients only need a single connection to the Eden server
- Acts as a reverse proxy for multiple MCP servers
- Maintains isolated namespaces for each server's tools and resources (using server IDs as namespace prefixes)
- Handles authentication and access control
- Enables human-in-the-loop approvals for sensitive operations
- Offers configurable rate limits and quotas
- Exposes a built-in UI for configuration, playground, and debugging

The server manages all external connections:
- Maintains direct connections to all configured MCP servers
- Maintains direct connections to all configured LLM vendors
- Handles all routing between clients and servers/vendors
- Manages authentication for all connections
- Provides unified approval interface for both tool and sampling requests

This design means that any MCP client can connect to Eden as if it were a standard MCP server, while Eden handles the complexity of routing requests to the appropriate downstream servers and vendors. All MCP features are properly namespaced and managed through the server.

#### 2. Configuration System
Eden uses a single JSON configuration file (`eden.json`) to define all aspects of the system:

##### Configuration Format
The core of Eden is a configuration specification that defines MCP servers and LLM vendors. The configuration format is defined in `spec.ts` using TypeScript types. This provides a clear specification that can be translated to JSON.

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

### Command Line Interface
The primary interface for Eden is the `eden` CLI tool, which follows a pattern similar to Docker, Makefiles, and other development tools:

1. **Primary Command**
   ```bash
   # Start the Eden server using eden.json configuration
   eden up
   ```

2. **Configuration Commands**
   ```bash
   # Initialize a new eden.json file
   eden init

   # Add a new server to the configuration
   eden add server <type> <id> [options]

   # Add a new LLM vendor
   eden add vendor <id> [options]

   # Update server or vendor settings
   eden set <id> <key> <value>

   # Remove a server or vendor
   eden remove <id>
   ```

3. **Utility Commands**
   ```bash
   # Validate the configuration file
   eden validate

   # Show server status
   eden status

   # View logs
   eden logs
   ```

The configuration file (`eden.json`) serves as the single source of truth for the entire system, making it easy to version control, share, and modify configurations.

### Built-in UI
The Eden server exposes a built-in web interface that provides:
- Configuration management
- Playground for testing MCP servers
- Inspector for debugging
- Approval interface for tool access

The UI is automatically available when the server is running and can be accessed through any web browser.

## Outstanding Topics

### MVP Implementation
1. **Core Server Development**
   - Basic MCP server implementation
   - Server connection management
   - Simple error handling
   - Basic monitoring
   - Built-in UI implementation

2. **Configuration System**
   - JSON configuration parser
   - Configuration validation
   - Default configuration generation

3. **CLI Tool**
   - `eden up` command
   - Configuration management commands
   - Basic monitoring commands

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

## References

### Model Control Protocol (MCP)
- [MCP Specification](https://github.com/wandb/mcp) - The core protocol that Eden implements and extends
- [MCP Python Client](https://github.com/wandb/mcp-python) - Reference implementation of MCP client
- [MCP Server](https://github.com/wandb/mcp-server) - Reference implementation of MCP server

### Key Design Decisions

#### Architecture
1. **Single Connection Point**
   - Clients only need to connect to the Eden server
   - Server maintains all connections to MCP servers and LLM vendors
   - Server is a fully conformant MCP server

2. **Configuration Management**
   - Configuration defined in TypeScript types (`spec.ts`)
   - Single JSON configuration file (`eden.json`)
   - Configuration cannot be changed while server is running
   - Changes require server restart

3. **Service Management**
   - Primary interface is the `eden` CLI tool
   - Server automatically starts UI
   - Service state is managed transparently

4. **LLM Integration**
   - Server maintains direct connections to LLM vendors
   - Vendors configured in the same config file as servers
   - Support for vendor-specific approval requirements

5. **Tool Access Control**
   - Per-tool settings (ALLOWED, DISALLOWED, NEEDS_APPROVAL)
   - Server-level defaults
   - Human-in-the-loop approval interface

#### Implementation Priorities
1. Core server functionality
2. Configuration system
3. CLI tool
4. Built-in UI
5. Server type implementations

## Getting Started
[Coming soon: Installation and quickstart guide]

## Documentation
[Coming soon: Detailed documentation and examples]

## Community
[Coming soon: Community guidelines and contribution information]
