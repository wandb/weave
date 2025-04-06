// Eden Configuration Specification
// This file defines the TypeScript types for Eden's configuration format
// Note: This is an MVP specification and is subject to iteration as the product develops

// Defines the possible settings for tool access control
export type ToolSetting = 'ALLOWED' | 'DISALLOWED' | 'NEEDS_APPROVAL';

// Maps tool names to their access control settings
// The '*' key can be used to set default settings for unspecified tools
export interface ToolSettings {
  [toolName: string]: ToolSetting;  // '*' can be used as a wildcard for default settings
}

// Configuration for connecting to an existing remote MCP server
export interface RemoteServerConfig {
  type: 'remote';  // Identifies this as a remote server configuration
  url: string;     // The URL where the MCP server is hosted
  auth?: {         // Optional authentication configuration
    type: string;  // The type of authentication (e.g., 'bearer')
    token: string; // The authentication token
  };
  tool_settings?: ToolSettings;  // Optional tool access control settings
}

// Configuration for running an MCP server in a Docker container
export interface DockerServerConfig {
  type: 'docker';  // Identifies this as a Docker server configuration
  image: string;   // The Docker image to run
  port?: number;   // Optional port mapping, defaults to 8000
  env?: Record<string, string>;  // Optional environment variables
  tool_settings?: ToolSettings;  // Optional tool access control settings
}

// Configuration for running an MCP server from a Python script
export interface ScriptServerConfig {
  type: 'script';  // Identifies this as a script server configuration
  path: string;    // Path to the Python script
  tool_settings?: ToolSettings;  // Optional tool access control settings
}

// Configuration for running an MCP server from a local directory
export interface LocalServerConfig {
  type: 'local';   // Identifies this as a local server configuration
  path: string;    // Path to the local MCP server project
  tool_settings?: ToolSettings;  // Optional tool access control settings
}

// Union type of all possible server configurations
export type ServerConfig = 
  | RemoteServerConfig 
  | DockerServerConfig 
  | ScriptServerConfig 
  | LocalServerConfig;

// The root configuration type for Eden
export interface EdenConfig {
  servers: {
    [serverId: string]: ServerConfig;  // Maps server IDs to their configurations
  };
} 