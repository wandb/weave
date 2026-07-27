// Fake Claude Code CLI speaking the `--output-format stream-json` protocol over
// stdio. The real `@anthropic-ai/claude-agent-sdk` `query()` spawns this in
// place of the bundled Claude Code binary (via the `pathToClaudeCodeExecutable`
// option set by main.mjs), so the host app runs fully offline and
// deterministically — no API key, no network, no real model call. We just emit
// a canned conversation as newline-delimited JSON `SDKMessage`s and exit. The
// integration under test should turn this stream into a `claude_agent_sdk.query`
// trace tree.
import process from 'node:process';

function emit(message) {
  process.stdout.write(JSON.stringify(message) + '\n');
}

const sessionId = 'fake-session';

// The SDK may send control_requests (e.g. an initialize handshake) on stdin.
// Answer each with a success control_response so the protocol doesn't stall.
let buffer = '';
process.stdin.on('data', chunk => {
  buffer += chunk.toString();
  let newline;
  while ((newline = buffer.indexOf('\n')) >= 0) {
    const line = buffer.slice(0, newline).trim();
    buffer = buffer.slice(newline + 1);
    if (!line) continue;
    let message;
    try {
      message = JSON.parse(line);
    } catch {
      continue;
    }
    if (message.type === 'control_request') {
      emit({
        type: 'control_response',
        response: {
          subtype: 'success',
          request_id: message.request_id,
          response: {},
        },
      });
    }
  }
});

// init system message (structured fields, no nested `message`)
emit({
  type: 'system',
  subtype: 'init',
  session_id: sessionId,
  uuid: 'u0',
  model: 'claude-fake',
  tools: ['Bash'],
  cwd: process.cwd(),
  apiKeySource: 'none',
  mcp_servers: [],
  slash_commands: [],
  permissionMode: 'default',
  output_style: 'default',
});
// assistant turn: thinking + text + a tool use
emit({
  type: 'assistant',
  session_id: sessionId,
  parent_tool_use_id: null,
  uuid: 'u1',
  message: {
    id: 'm1',
    type: 'message',
    role: 'assistant',
    model: 'claude-fake',
    stop_reason: 'tool_use',
    content: [
      {type: 'thinking', thinking: 'I should list the files.'},
      {type: 'text', text: 'Let me look.'},
      {type: 'tool_use', id: 'tool-1', name: 'Bash', input: {command: 'ls'}},
    ],
  },
});
// tool result, delivered as a user message
emit({
  type: 'user',
  session_id: sessionId,
  parent_tool_use_id: null,
  uuid: 'u2',
  message: {
    role: 'user',
    content: [
      {
        type: 'tool_result',
        tool_use_id: 'tool-1',
        content: 'main.mjs\npackage.json',
        is_error: false,
      },
    ],
  },
});
// final assistant turn
emit({
  type: 'assistant',
  session_id: sessionId,
  parent_tool_use_id: null,
  uuid: 'u3',
  message: {
    id: 'm2',
    type: 'message',
    role: 'assistant',
    model: 'claude-fake',
    stop_reason: 'end_turn',
    content: [{type: 'text', text: 'There are two files.'}],
  },
});
// terminal result with per-model (camelCase) usage
emit({
  type: 'result',
  subtype: 'success',
  session_id: sessionId,
  uuid: 'u4',
  is_error: false,
  result: 'There are two files.',
  duration_ms: 7,
  duration_api_ms: 5,
  num_turns: 2,
  total_cost_usd: 0.0002,
  stop_reason: 'end_turn',
  usage: {input_tokens: 8, output_tokens: 12},
  modelUsage: {
    'claude-fake': {
      inputTokens: 8,
      outputTokens: 12,
      cacheReadInputTokens: 0,
      cacheCreationInputTokens: 0,
      webSearchRequests: 0,
      costUSD: 0.0002,
      contextWindow: 200000,
      maxOutputTokens: 8192,
    },
  },
  permission_denials: [],
});

// Give the SDK a moment to drain stdout, then exit cleanly.
setTimeout(() => process.exit(0), 100);
