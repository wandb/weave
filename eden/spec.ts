// Eden Configuration Specification
// This file defines the TypeScript types for Eden's configuration format
// Note: This is an MVP specification and is subject to iteration as the product develops

/** Defines the possible settings for tool access control */
export type ToolSetting = 'ALLOWED' | 'DISALLOWED' | 'NEEDS_APPROVAL';

/** 
 * Maps tool names to their access control settings
 * The '*' key can be used to set default settings for unspecified tools
 */
export interface ToolSettings {
  [toolName: string]: ToolSetting;
}

/** Configuration for connecting to an existing remote MCP server */
export interface RemoteServerConfig {
  /** Identifies this as a remote server configuration */
  type: 'remote';
  /** The URL where the MCP server is hosted */
  url: string;
  /** Optional authentication configuration */
  auth?: {
    /** The type of authentication (e.g., 'bearer') */
    type: string;
    /** The authentication token */
    token: string;
  };
  /** Optional tool access control settings */
  tool_settings?: ToolSettings;
}

/** Configuration for running an MCP server in a Docker container */
export interface DockerServerConfig {
  /** Identifies this as a Docker server configuration */
  type: 'docker';
  /** The Docker image to run */
  image: string;
  /** Optional port mapping, defaults to 8000 */
  port?: number;
  /** Optional environment variables */
  env?: Record<string, string>;
  /** Optional tool access control settings */
  tool_settings?: ToolSettings;
}

/** Configuration for running an MCP server from a Python script */
export interface ScriptServerConfig {
  /** Identifies this as a script server configuration */
  type: 'script';
  /** Path to the Python script */
  path: string;
  /** Optional tool access control settings */
  tool_settings?: ToolSettings;
}

/** Configuration for running an MCP server from a local directory */
export interface LocalServerConfig {
  /** Identifies this as a local server configuration */
  type: 'local';
  /** Path to the local MCP server project */
  path: string;
  /** Optional tool access control settings */
  tool_settings?: ToolSettings;
}

/** Union type of all possible server configurations */
export type ServerConfig = 
  | RemoteServerConfig 
  | DockerServerConfig 
  | ScriptServerConfig 
  | LocalServerConfig;

/** The root configuration type for Eden */
export interface EdenConfig {
  /** Maps server IDs to their configurations */
  servers: {
    [serverId: string]: ServerConfig;
  };
} 