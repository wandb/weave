import {randomUUID} from 'crypto';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';

import {fixturePath, genProjectId, launchAppFrom} from './utils';

type CapturedSpan = {
  name: string;
};

// Smoke test for the Claude Agent SDK integration's packaging + module-loading.
// Like the other hostApps tests, its job is narrow: confirm that launching a
// real ESM host app under `node --import=weave/instrument` actually patches
// `@anthropic-ai/claude-agent-sdk`'s `query()` and emits the integration's root
// agent span through the real OTel pipeline. The detailed span-tree, usage, and
// tool-call shape are asserted one layer down in the tracer unit test
// (src/__tests__/integrations/claude-agent-sdk/otelTracer.test.ts), which drives
// the tracer directly against mocked SDK messages — cheaper and more exhaustive
// than re-asserting shape inside a spawned host app.
describe('hostApps — claude-agent-sdk', () => {
  test('auto-instruments the real @anthropic-ai/claude-agent-sdk query() and emits the agent root span', async () => {
    const projectId = genProjectId();
    // The fixture writes its captured OTel spans here (it installs a capturing
    // span processor via weave.init), so we observe the real emission path
    // without standing up an OTLP receiver.
    const spanFile = path.join(os.tmpdir(), `cas-otel-${randomUUID()}.json`);

    const result = await launchAppFrom({
      path: fixturePath('claude-agent-sdk'),
      projectId,
      extraEnv: {SPAN_OUTPUT_FILE: spanFile},
    });
    if (result.exitCode !== 0) {
      throw new Error(
        `claude-agent-sdk fixture exited ${result.exitCode}\n` +
          `stdout:\n${result.stdout}\nstderr:\n${result.stderr}`
      );
    }

    const spans = JSON.parse(
      fs.readFileSync(spanFile, 'utf8')
    ) as CapturedSpan[];
    fs.rmSync(spanFile, {force: true});

    // The integration fired end-to-end: launching under
    // `--import=weave/instrument` patched query() and the tracer emitted its
    // root agent span through the real OTel pipeline. That's the entire
    // packaging / module-loading contract this layer protects.
    const emittedAgentRoot = spans.some(
      s => s.name === 'invoke_agent claude_agent_sdk'
    );
    expect(emittedAgentRoot).toBe(true);
  }, 60_000);
});
