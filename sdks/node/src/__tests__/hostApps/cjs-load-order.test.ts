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

  test('the exit listener warns when the app exits right after init()', async () => {
    const result = await launch('start-forced-exit');
    expect(result.exitCode).toBe(0);
    expect(result.stderr).toContain(
      "Weave: 'openai' was loaded before 'weave'"
    );
  }, 60_000);

  test('a prototype-patched library warns until it is required again', async () => {
    const once = await launch('start-prototype-patch');
    expect(once.stdout).toContain('patched: false');
    expect(once.stderr).toContain(
      "Weave: '@anthropic-ai/sdk' was loaded before 'weave'"
    );

    const again = await launch('start-prototype-patch-again');
    expect(again.stdout).toContain('patched: true');
    expect(again.stderr).not.toContain('was loaded before');
  }, 60_000);
});
