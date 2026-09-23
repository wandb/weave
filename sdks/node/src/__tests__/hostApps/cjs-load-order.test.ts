import {fixturePath, genProjectId, launchAppFrom} from './utils';

function launch(scriptName?: string) {
  return launchAppFrom({
    path: fixturePath('cjs-load-order'),
    projectId: genProjectId(),
    scriptName,
  });
}

describe('hostApps — cjs-load-order', () => {
  test('init() warns when the library was required before weave', async () => {
    const result = await launch();
    expect(result.exitCode).toBe(0);
    expect(result.stderr).toContain(
      "Weave: 'openai' was loaded before 'weave'"
    );
  }, 60_000);

  test('init() stays quiet when weave was required first', async () => {
    const result = await launch('start-weave-first');
    expect(result.exitCode).toBe(0);
    expect(result.stderr).not.toContain('was loaded before');
  }, 60_000);

  test('init() stays quiet when a second copy of weave loads after the library', async () => {
    const result = await launch('start-weave-twice');
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain('create: wrappedWithAgents');
    expect(result.stderr).not.toContain('was loaded before');
  }, 60_000);

  test('init() stays quiet when the client is wrapped explicitly before it', async () => {
    const result = await launch('start-wrap-before-init');
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain('create: wrappedWithAgents');
    expect(result.stderr).not.toContain('was loaded before');
  }, 60_000);

  test('init() stays quiet when the client is wrapped explicitly right after it', async () => {
    const result = await launch('start-wrap-after-init');
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain('create: wrappedWithAgents');
    expect(result.stderr).not.toContain('was loaded before');
  }, 60_000);
});
