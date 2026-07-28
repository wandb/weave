import * as vm from 'vm';
import {Dataset, op} from 'weave';
import type {Op} from 'weave';
import {initWithCustomTraceServer} from './clientMock';
import {InMemoryTraceServer} from './helpers/inMemoryTraceServer';

// Asserted here, at the serializer, and not per integration: an integration test
// only covers the integrations that exist today, and `self` is recorded by the
// `op` decorator too.

const SENTINEL = 'sentinel-value';

class InnerState {
  token = SENTINEL;
}

class OuterHandle {
  inner = new InnerState();
}

describe('serializing objects the SDK does not own', () => {
  const projectId = 'test-project';
  let traceServer: InMemoryTraceServer;

  beforeEach(() => {
    traceServer = new InMemoryTraceServer();
    initWithCustomTraceServer(projectId, traceServer);
  });

  test('a class instance bound to an op is recorded as a type marker', async () => {
    const handle = new OuterHandle();
    const create = op(
      handle,
      async (_params: {model: string}) => ({ok: true}),
      {
        name: 'create',
        parameterNames: 'useParam0Object',
      }
    );

    await create({model: 'test-model'});

    const calls = await traceServer.getCalls(projectId);
    expect(calls).toHaveLength(1);
    expect(calls[0].inputs).toEqual({
      self: '<OuterHandle>',
      model: 'test-model',
    });
    expect(JSON.stringify(calls[0])).not.toContain(SENTINEL);
  });

  test('a user class holding a nested instance is recorded as a type marker', async () => {
    class Agent {
      handle = new OuterHandle();
      ask: Op<(question: string) => Promise<string>>;

      constructor() {
        this.ask = op(this, this.askImpl);
      }

      private async askImpl(question: string) {
        return `answered: ${question}`;
      }
    }

    await new Agent().ask('hello');

    const calls = await traceServer.getCalls(projectId);
    expect(calls).toHaveLength(1);
    expect(calls[0].inputs).toEqual({self: '<Agent>', arg0: 'hello'});
    expect(JSON.stringify(calls[0])).not.toContain(SENTINEL);
  });

  test('class instances nested in an argument are recorded as a type marker', async () => {
    const call = op(
      async (_params: {handle: OuterHandle; tools: OuterHandle[]}) => 'ok',
      {name: 'call', parameterNames: 'useParam0Object'}
    );

    await call({handle: new OuterHandle(), tools: [new OuterHandle()]});

    const calls = await traceServer.getCalls(projectId);
    expect(calls).toHaveLength(1);
    expect(calls[0].inputs).toEqual({
      handle: '<OuterHandle>',
      tools: ['<OuterHandle>'],
    });
    expect(JSON.stringify(calls[0])).not.toContain(SENTINEL);
  });

  test('a class instance passed as the whole argument object is recorded as a type marker', async () => {
    const call = op(async (_params: OuterHandle) => 'ok', {
      name: 'call',
      parameterNames: 'useParam0Object',
    });

    await call(new OuterHandle());

    const calls = await traceServer.getCalls(projectId);
    expect(calls).toHaveLength(1);
    expect(calls[0].inputs).toEqual({arg0: '<OuterHandle>'});
    expect(JSON.stringify(calls[0])).not.toContain(SENTINEL);
  });

  test('a Weave object held by a class instance in inputs is not uploaded', async () => {
    class Holder {
      dataset = new Dataset({name: 'held-dataset', rows: [{a: 1}]});
    }
    const call = op(async (_holder: Holder) => 'ok', {name: 'call'});

    await call(new Holder());

    const calls = await traceServer.getCalls(projectId);
    expect(calls[0].inputs).toEqual({arg0: '<Holder>'});
    // Nothing in the call can reference a ref saved through the holder, so it
    // is never saved in the first place.
    await expect(
      traceServer.obj.objReadObjReadPost({
        project_id: projectId,
        object_id: 'held-dataset',
      })
    ).rejects.toThrow('Object not found');
  });

  test('a saved Weave object in inputs is still recorded as a ref', async () => {
    const dataset = new Dataset({
      name: 'serialization-dataset',
      rows: [{a: 1}],
    });
    const call = op(async (_rows: Dataset<{a: number}>) => 'ok', {
      name: 'call',
    });

    await call(dataset);

    const calls = await traceServer.getCalls(projectId);
    expect(calls).toHaveLength(1);
    expect(calls[0].inputs.arg0).toMatch(
      /^weave:\/\/\/.*\/object\/serialization-dataset:/
    );
  });

  test('built-in instances in inputs are recorded as a type marker', async () => {
    const echo = op(async (_value: unknown) => 'ok', {name: 'echo'});

    await echo({
      when: new Date('2026-07-28T00:00:00Z'),
      seen: new Map([['a', 1]]),
      bytes: Buffer.from('hi'),
      anonymous: new (class {})(),
    });

    const calls = await traceServer.getCalls(projectId);
    expect(calls).toHaveLength(1);
    expect(calls[0].inputs).toEqual({
      arg0: {
        when: '<Date>',
        seen: '<Map>',
        bytes: '<Buffer>',
        anonymous: '<anonymous>',
      },
    });
  });

  test('plain objects in inputs are still recorded in full', async () => {
    const nullPrototype = Object.create(null);
    nullPrototype.kept = true;
    const payload = {
      _id: 'underscore keys of plain objects are kept',
      nested: {list: [1, {deep: true}], nullValue: null},
      nullPrototype,
      // Built in another realm, so its prototype is not this realm's
      // `Object.prototype`, and it still counts as plain.
      otherRealm: vm.runInNewContext('({kept: true})'),
    };
    const echo = op(async (value: unknown) => value, {name: 'echo'});

    await echo(payload);

    const calls = await traceServer.getCalls(projectId);
    expect(calls).toHaveLength(1);
    expect(calls[0].inputs).toEqual({arg0: payload});
  });

  test('a class instance returned from an op is still recorded in full', async () => {
    class ProviderResponse {
      text = 'hello';
      usage = {tokens: 1};
    }
    const generate = op(async () => new ProviderResponse(), {name: 'generate'});

    await generate();

    const calls = await traceServer.getCalls(projectId);
    expect(calls).toHaveLength(1);
    expect(calls[0].output).toEqual({text: 'hello', usage: {tokens: 1}});
  });
});
