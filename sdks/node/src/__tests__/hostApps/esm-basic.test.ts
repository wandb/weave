import {fixturePath, genProjectId, getCalls, launchAppFrom} from './utils';

describe('hostApps — esm-basic', () => {
  test('import("weave"), run an op, and emit a captured trace', async () => {
    const projectId = genProjectId();
    const result = await launchAppFrom({
      path: fixturePath('esm-basic'),
      projectId,
    });
    if (result.exitCode !== 0) {
      throw new Error(
        `esm-basic exited ${result.exitCode}\n` +
          `stdout:\n${result.stdout}\nstderr:\n${result.stderr}`
      );
    }
    // Confirm the fixture's `myOp` actually executed and emitted a trace
    // the mock captured under our project_id.
    const calls = await getCalls(projectId);
    expect(calls.length).toBeGreaterThanOrEqual(1);
    expect(
      calls.some(c => typeof c.op_name === 'string' && c.op_name.includes('myOp'))
    ).toBe(true);
  }, 60_000);
});
