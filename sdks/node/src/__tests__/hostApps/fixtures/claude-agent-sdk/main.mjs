// Claude Agent SDK ESM host app. Launched via
//   node --import=weave/instrument main.mjs
// (declared in this fixture's package.json `scripts.start`) so the ESM loader
// hook is in place and patches `@anthropic-ai/claude-agent-sdk`'s `query()` as
// it is imported — the same invocation a real ESM consumer uses.
//
// query() is pointed at a fake Claude Code executable (fake-claude-cli.mjs)
// that emits a canned stream-json conversation, so this runs fully offline:
// no API key, no network, no real model call. The integration should still
// produce a `claude_agent_sdk.query` trace tree that the mock captures.
//
// Configuration comes from env vars set by the test driver:
//   WF_TRACE_SERVER_URL — the spawned Python trace-server mock
//   WANDB_API_KEY       — dummy; the mock accepts any auth
//   WANDB_PROJECT       — `entity/project`, unique per-test for isolation
import * as weave from 'weave';
import {query} from '@anthropic-ai/claude-agent-sdk';
import {fileURLToPath} from 'node:url';

const client = await weave.init(process.env.WANDB_PROJECT);

const fakeCli = fileURLToPath(
  new URL('./fake-claude-cli.mjs', import.meta.url)
);

for await (const message of query({
  prompt: 'What files are in this directory?',
  options: {pathToClaudeCodeExecutable: fakeCli, executable: 'node'},
})) {
  console.log(`message: ${message.type}`);
}

await client.waitForBatchProcessing();
