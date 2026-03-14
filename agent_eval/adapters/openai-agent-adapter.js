#!/usr/bin/env node
/**
 * OpenAI Agent Adapter for agent_eval
 * 
 * A simple agent that uses the OpenAI API directly to execute tasks.
 * This works reliably in Docker containers where Codex CLI has networking issues.
 * 
 * Environment variables:
 *   AGENT_EVAL_PROMPT      - The user prompt to execute
 *   AGENT_EVAL_SKILL_PATH  - Path to skill directory
 *   AGENT_EVAL_WORKDIR     - Working directory (default: /workspace)
 *   AGENT_EVAL_MODEL       - Model to use (default: gpt-4o)
 *   OPENAI_API_KEY         - OpenAI API key
 */

const https = require('https');
const fs = require('fs');
const path = require('path');
const { execSync, spawn } = require('child_process');

// Configuration
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
const PROMPT = process.env.AGENT_EVAL_PROMPT;
const SKILL_PATH = process.env.AGENT_EVAL_SKILL_PATH || '/skill';
const WORKDIR = process.env.AGENT_EVAL_WORKDIR || '/workspace';
const MODEL = process.env.AGENT_EVAL_MODEL || 'gpt-4o';
const MAX_TURNS = parseInt(process.env.AGENT_EVAL_MAX_TURNS || '10', 10);
const ARTIFACTS_DIR = '/artifacts';

// Ensure artifacts directory exists
if (!fs.existsSync(ARTIFACTS_DIR)) {
  fs.mkdirSync(ARTIFACTS_DIR, { recursive: true });
}

// Trajectory log
const trajectoryPath = path.join(ARTIFACTS_DIR, 'trajectory.jsonl');
const trajectoryStream = fs.createWriteStream(trajectoryPath, { flags: 'a' });

function log(event) {
  const entry = { timestamp: new Date().toISOString(), ...event };
  trajectoryStream.write(JSON.stringify(entry) + '\n');
  console.error(JSON.stringify(entry));
}

// Load skill instructions if available
function loadSkillInstructions() {
  const skillFile = path.join(SKILL_PATH, 'SKILL.md');
  if (fs.existsSync(skillFile)) {
    return fs.readFileSync(skillFile, 'utf-8');
  }
  return '';
}

// Available tools for the agent
const tools = [
  {
    type: 'function',
    function: {
      name: 'execute_command',
      description: 'Execute a shell command in the workspace directory',
      parameters: {
        type: 'object',
        properties: {
          command: {
            type: 'string',
            description: 'The shell command to execute'
          }
        },
        required: ['command']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'write_file',
      description: 'Write content to a file',
      parameters: {
        type: 'object',
        properties: {
          path: {
            type: 'string',
            description: 'The file path relative to the workspace'
          },
          content: {
            type: 'string',
            description: 'The content to write to the file'
          }
        },
        required: ['path', 'content']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'read_file',
      description: 'Read the contents of a file',
      parameters: {
        type: 'object',
        properties: {
          path: {
            type: 'string',
            description: 'The file path relative to the workspace'
          }
        },
        required: ['path']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'list_files',
      description: 'List files in a directory',
      parameters: {
        type: 'object',
        properties: {
          path: {
            type: 'string',
            description: 'The directory path relative to the workspace (default: ".")'
          }
        }
      }
    }
  }
];

// Tool implementations
function executeCommand(command) {
  log({ type: 'tool_call', tool: 'execute_command', args: { command } });
  try {
    const output = execSync(command, { 
      cwd: WORKDIR, 
      encoding: 'utf-8',
      timeout: 30000,
      maxBuffer: 1024 * 1024
    });
    log({ type: 'tool_result', tool: 'execute_command', success: true, output: output.substring(0, 2000) });
    return { success: true, output };
  } catch (error) {
    const result = { 
      success: false, 
      error: error.message,
      stdout: error.stdout || '',
      stderr: error.stderr || '',
      exitCode: error.status
    };
    log({ type: 'tool_result', tool: 'execute_command', ...result });
    return result;
  }
}

function writeFile(filePath, content) {
  log({ type: 'tool_call', tool: 'write_file', args: { path: filePath, contentLength: content.length } });
  try {
    const fullPath = path.resolve(WORKDIR, filePath);
    const dir = path.dirname(fullPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(fullPath, content);
    log({ type: 'tool_result', tool: 'write_file', success: true, path: fullPath });
    return { success: true, path: fullPath };
  } catch (error) {
    log({ type: 'tool_result', tool: 'write_file', success: false, error: error.message });
    return { success: false, error: error.message };
  }
}

function readFile(filePath) {
  log({ type: 'tool_call', tool: 'read_file', args: { path: filePath } });
  try {
    const fullPath = path.resolve(WORKDIR, filePath);
    const content = fs.readFileSync(fullPath, 'utf-8');
    log({ type: 'tool_result', tool: 'read_file', success: true, contentLength: content.length });
    return { success: true, content };
  } catch (error) {
    log({ type: 'tool_result', tool: 'read_file', success: false, error: error.message });
    return { success: false, error: error.message };
  }
}

function listFiles(dirPath = '.') {
  log({ type: 'tool_call', tool: 'list_files', args: { path: dirPath } });
  try {
    const fullPath = path.resolve(WORKDIR, dirPath);
    const files = fs.readdirSync(fullPath, { withFileTypes: true });
    const result = files.map(f => ({
      name: f.name,
      type: f.isDirectory() ? 'directory' : 'file'
    }));
    log({ type: 'tool_result', tool: 'list_files', success: true, count: result.length });
    return { success: true, files: result };
  } catch (error) {
    log({ type: 'tool_result', tool: 'list_files', success: false, error: error.message });
    return { success: false, error: error.message };
  }
}

function handleToolCall(toolCall) {
  const name = toolCall.function.name;
  const args = JSON.parse(toolCall.function.arguments);
  
  switch (name) {
    case 'execute_command':
      return executeCommand(args.command);
    case 'write_file':
      return writeFile(args.path, args.content);
    case 'read_file':
      return readFile(args.path);
    case 'list_files':
      return listFiles(args.path);
    default:
      return { success: false, error: `Unknown tool: ${name}` };
  }
}

// OpenAI API call
function callOpenAI(messages) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify({
      model: MODEL,
      messages,
      tools,
      max_tokens: 4096
    });

    const options = {
      hostname: 'api.openai.com',
      path: '/v1/chat/completions',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${OPENAI_API_KEY}`,
        'Content-Length': Buffer.byteLength(data)
      }
    };

    const req = https.request(options, (res) => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        if (res.statusCode !== 200) {
          reject(new Error(`API error ${res.statusCode}: ${body}`));
          return;
        }
        try {
          resolve(JSON.parse(body));
        } catch (e) {
          reject(new Error(`Failed to parse response: ${e.message}`));
        }
      });
    });

    req.on('error', reject);
    req.write(data);
    req.end();
  });
}

// Main agent loop
async function runAgent() {
  if (!OPENAI_API_KEY) {
    console.error('Error: OPENAI_API_KEY is required');
    process.exit(1);
  }
  
  if (!PROMPT) {
    console.error('Error: AGENT_EVAL_PROMPT is required');
    process.exit(1);
  }

  log({ type: 'agent_started', model: MODEL, prompt: PROMPT });

  // Build system prompt
  const skillInstructions = loadSkillInstructions();
  const systemPrompt = `You are a helpful coding assistant that can execute shell commands and manipulate files.
You are working in the directory: ${WORKDIR}

${skillInstructions ? `## Skill Instructions\n${skillInstructions}\n` : ''}

When you have completed the task, respond with a final message summarizing what you did.
Use the available tools to complete the user's request.`;

  const messages = [
    { role: 'system', content: systemPrompt },
    { role: 'user', content: PROMPT }
  ];

  let turn = 0;
  while (turn < MAX_TURNS) {
    turn++;
    log({ type: 'turn_started', turn });

    try {
      const response = await callOpenAI(messages);
      const choice = response.choices[0];
      const message = choice.message;

      log({ type: 'assistant_message', turn, content: message.content, tool_calls: message.tool_calls?.length || 0 });

      messages.push(message);

      // Check if we're done
      if (choice.finish_reason === 'stop' && !message.tool_calls) {
        log({ type: 'agent_completed', turn, final_message: message.content });
        break;
      }

      // Process tool calls
      if (message.tool_calls) {
        for (const toolCall of message.tool_calls) {
          const result = handleToolCall(toolCall);
          messages.push({
            role: 'tool',
            tool_call_id: toolCall.id,
            content: JSON.stringify(result)
          });
        }
      }
    } catch (error) {
      log({ type: 'error', turn, error: error.message });
      console.error(`Error on turn ${turn}: ${error.message}`);
      break;
    }
  }

  if (turn >= MAX_TURNS) {
    log({ type: 'max_turns_reached', turn });
  }

  // Copy workspace to artifacts
  const workspaceArtifacts = path.join(ARTIFACTS_DIR, 'workspace');
  if (!fs.existsSync(workspaceArtifacts)) {
    fs.mkdirSync(workspaceArtifacts, { recursive: true });
  }
  
  try {
    execSync(`cp -r ${WORKDIR}/* ${workspaceArtifacts}/ 2>/dev/null || true`, { encoding: 'utf-8' });
    log({ type: 'artifacts_saved' });
  } catch (e) {
    log({ type: 'artifacts_save_error', error: e.message });
  }

  trajectoryStream.end();
}

runAgent().catch(err => {
  console.error('Agent failed:', err);
  process.exit(1);
});
