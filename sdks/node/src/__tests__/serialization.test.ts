import * as vm from 'vm';
import {Dataset, op} from 'weave';
import type {Op} from 'weave';
import {requireGlobalClient} from '../clientApi';
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

  test('an array argument object keeps being spread', async () => {
    const call = op(async (_params: string[]) => 'ok', {
      name: 'call',
      parameterNames: 'useParam0Object',
    });

    await call(['a', 'b']);

    const calls = await traceServer.getCalls(projectId);
    expect(calls[0].inputs).toEqual({0: 'a', 1: 'b'});
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
      constructor(name: string) {
        this.dataset = new Dataset({name, rows: [{a: 1}]});
      }
      dataset: Dataset<{a: number}>;
    }
    const uploaded = jest.spyOn(traceServer.objects, 'create');
    const call = op(
      async (_params: {direct: Holder; nested: Holder[]}) => 'ok',
      {name: 'call', parameterNames: 'useParam0Object'}
    );

    await call({
      direct: new Holder('held-directly'),
      nested: [new Holder('held-in-an-array')],
    });

    const calls = await traceServer.getCalls(projectId);
    expect(calls[0].inputs).toEqual({
      direct: '<Holder>',
      nested: ['<Holder>'],
    });
    // Nothing in the call can reference a ref saved through the holder, so it
    // is never saved in the first place.
    expect(uploaded.mock.calls.map(([req]) => req.obj.object_id)).not.toContain(
      'held-directly'
    );
    expect(uploaded.mock.calls.map(([req]) => req.obj.object_id)).not.toContain(
      'held-in-an-array'
    );
  });

  test('a saved Weave object in inputs is still recorded as a ref', async () => {
    const dataset = new Dataset({
      name: 'serialization-dataset',
      rows: [{a: 1}],
    });
    // Bound as well as passed, because `self` is the key the app reads as a ref.
    const call = op(dataset, async (_rows: Dataset<{a: number}>) => 'ok', {
      name: 'call',
    });

    await call(dataset);

    const ref = expect.stringMatching(
      /^weave:\/\/\/test-project\/object\/serialization-dataset:[0-9a-f-]+$/
    );
    const calls = await traceServer.getCalls(projectId);
    expect(calls).toHaveLength(1);
    expect(calls[0].inputs).toEqual({self: ref, arg0: ref});
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

  test('publishing a class instance still records its fields', async () => {
    class Config {
      region = 'us-east';
      retries = 3;
    }

    await requireGlobalClient().publish(new Config(), 'published-config');

    const read = await traceServer.objects.read({
      project_id: projectId,
      object_id: 'published-config',
    });
    // Only call inputs stop at class instances; publishing one is an explicit
    // request to store it.
    expect(read.obj.val).toEqual({region: 'us-east', retries: 3});
  });

  test('a class instance returned from an op is still recorded in full', async () => {
    class ProviderResponse {
      text = 'hello';
      // A Weave value held by the response still gets its ref, which is what
      // the save pre-pass is for on the output side.
      dataset = new Dataset({name: 'returned-dataset', rows: [{a: 1}]});
    }
    const generate = op(async () => new ProviderResponse(), {name: 'generate'});

    await generate();

    const calls = await traceServer.getCalls(projectId);
    expect(calls).toHaveLength(1);
    expect(calls[0].output).toEqual({
      text: 'hello',
      dataset: expect.stringMatching(
        /^weave:\/\/\/test-project\/object\/returned-dataset:[0-9a-f-]+$/
      ),
    });
  });
});
