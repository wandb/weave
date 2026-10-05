import {fixturePath, genProjectId, getCalls, launchAppFrom} from './utils';

describe('hostApps — openai-double-wrap', () => {
  test('a client wrapped by two copies of weave and wrapOpenAI() logs one call', async () => {
    const projectId = genProjectId();
    const result = await launchAppFrom({
      path: fixturePath('openai-double-wrap'),
      projectId,
    });
    if (result.exitCode !== 0) {
      throw new Error(
        `openai-double-wrap exited ${result.exitCode}\n` +
          `stdout:\n${result.stdout}\nstderr:\n${result.stderr}`
      );
    }
    expect(result.stdout).toContain('reply: Paris');
    const calls = await getCalls(projectId);
    expect(calls).toHaveLength(1);
    expect(calls[0].op_name).toContain('openai.chat.completions.create');
  }, 60_000);
});
