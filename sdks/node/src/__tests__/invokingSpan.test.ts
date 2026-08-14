import {AsyncLocalStorage} from 'async_hooks';
import {
  context,
  type Context,
  type ContextManager,
  ROOT_CONTEXT,
  type Tracer,
} from '@opentelemetry/api';
import {
  BasicTracerProvider,
  type IdGenerator,
  type Sampler,
  SamplingDecision,
} from '@opentelemetry/sdk-trace-base';

import {INVOKING_SPAN_ATTR_KEY} from '../constants';
import {op} from '../op';
import {packageVersion} from '../utils/packageVersion';
import {initWithCustomTraceServer} from './clientMock';
import {InMemoryTraceServer} from './helpers/inMemoryTraceServer';

/**
 * The ambient source answers only while a context manager is registered, and
 * `@opentelemetry/context-async-hooks` is not a dependency of this SDK. This is
 * the part of it these tests need — what a user running the OTel Node SDK has.
 */
class TestContextManager implements ContextManager {
  private readonly storage = new AsyncLocalStorage<Context>();

  active(): Context {
    return this.storage.getStore() ?? ROOT_CONTEXT;
  }

  with<A extends unknown[], F extends (...args: A) => ReturnType<F>>(
    ctx: Context,
    fn: F,
    thisArg?: ThisParameterType<F>,
    ...args: A
  ): ReturnType<F> {
    return this.storage.run(ctx, () => fn.call(thisArg, ...args));
  }

  bind<T>(_ctx: Context, target: T): T {
    return target;
  }

  enable(): this {
    return this;
  }

  disable(): this {
    this.storage.disable();
    return this;
  }
}

/** Alive but never exported — the decision Weave records nothing for. */
const recordOnlySampler: Sampler = {
  shouldSample: () => ({decision: SamplingDecision.RECORD}),
  toString: () => 'RecordOnlySampler',
};

/** The all-zero identity a custom generator can produce. */
const zeroIdGenerator: IdGenerator = {
  generateTraceId: () => '0'.repeat(32),
  generateSpanId: () => '0'.repeat(16),
};

const PROJECT_ID = 'test-project';

// Every test goes through the public path — run an op, read the stored call —
// because the span has to be read at a point `createCall` reaches before it
// awaits, which a direct call to the resolver cannot show.
describe('invoking span', () => {
  let traceServer: InMemoryTraceServer;

  beforeEach(() => {
    traceServer = new InMemoryTraceServer();
    initWithCustomTraceServer(PROJECT_ID, traceServer);
    context.setGlobalContextManager(new TestContextManager());
  });

  afterEach(() => {
    // Jest runs the files in one process, so a registration left behind here
    // would make the ambient source answer in every later file.
    context.disable();
  });

  /** A tracer from a provider the user owns, the way BYO-OTel reaches us. */
  function userTracer(
    config: {
      sampler?: Sampler;
      idGenerator?: IdGenerator;
    } = {}
  ): Tracer {
    return new BasicTracerProvider(config).getTracer('user');
  }

  /** The `weave` attributes of the stored call named `opName`. */
  async function weaveAttributes(opName: string): Promise<Record<string, any>> {
    const calls = await traceServer.getCalls(PROJECT_ID);
    const call = calls.find(c => c.op_name.includes(opName));
    if (!call) {
      throw new Error(`no stored call for op ${opName}`);
    }
    return call.attributes.weave;
  }

  function tracedOp(name: string, attributes?: Record<string, any>) {
    return op(async () => 'done', {name, attributes});
  }

  test('records the span a call started inside', async () => {
    const {traceId, spanId} = await userTracer().startActiveSpan(
      'user_work',
      async span => {
        await tracedOp('lookup')();
        span.end();
        return span.spanContext();
      }
    );

    expect(await weaveAttributes('lookup')).toEqual({
      client_version: packageVersion,
      source: 'js-sdk',
      [INVOKING_SPAN_ATTR_KEY]: {trace_id: traceId, span_id: spanId},
    });
  });

  test('records nothing outside a span', async () => {
    await tracedOp('lookup')();

    expect(await weaveAttributes('lookup')).not.toHaveProperty(
      INVOKING_SPAN_ATTR_KEY
    );
  });

  test('records nothing for a span that will not be exported', async () => {
    const tracer = userTracer({sampler: recordOnlySampler});
    await tracer.startActiveSpan('user_work', async span => {
      await tracedOp('lookup')();
      span.end();
    });

    expect(await weaveAttributes('lookup')).not.toHaveProperty(
      INVOKING_SPAN_ATTR_KEY
    );
  });

  test('records nothing for a span that has already ended', async () => {
    await userTracer().startActiveSpan('user_work', async span => {
      span.end();
      await tracedOp('lookup')();
    });

    expect(await weaveAttributes('lookup')).not.toHaveProperty(
      INVOKING_SPAN_ATTR_KEY
    );
  });

  test('records nothing for an all-zero span identity', async () => {
    const tracer = userTracer({idGenerator: zeroIdGenerator});
    await tracer.startActiveSpan('user_work', async span => {
      await tracedOp('lookup')();
      span.end();
    });

    expect(await weaveAttributes('lookup')).not.toHaveProperty(
      INVOKING_SPAN_ATTR_KEY
    );
  });

  test('records the span on every call started inside it, not just the first', async () => {
    const inner = tracedOp('inner');
    const outer = op(async () => inner(), {name: 'outer'});
    await userTracer().startActiveSpan('user_work', async span => {
      await outer();
      span.end();
    });

    const expected = (await weaveAttributes('outer'))[INVOKING_SPAN_ATTR_KEY];
    expect(expected).toEqual({
      trace_id: expect.any(String),
      span_id: expect.any(String),
    });
    expect((await weaveAttributes('inner'))[INVOKING_SPAN_ATTR_KEY]).toEqual(
      expected
    );
  });

  test('records the span across an await inside it', async () => {
    await userTracer().startActiveSpan('user_work', async span => {
      await new Promise(resolve => setTimeout(resolve, 0));
      await tracedOp('lookup')();
      span.end();
    });

    expect(await weaveAttributes('lookup')).toHaveProperty(
      INVOKING_SPAN_ATTR_KEY
    );
  });

  test('overwrites a value a caller supplied under the key', async () => {
    const supplied = {
      weave: {[INVOKING_SPAN_ATTR_KEY]: {trace_id: 'ff', span_id: 'ff'}},
    };
    const {traceId, spanId} = await userTracer().startActiveSpan(
      'user_work',
      async span => {
        await tracedOp('inside', supplied)();
        span.end();
        return span.spanContext();
      }
    );
    await tracedOp('outside', supplied)();

    expect((await weaveAttributes('inside'))[INVOKING_SPAN_ATTR_KEY]).toEqual({
      trace_id: traceId,
      span_id: spanId,
    });
    expect(await weaveAttributes('outside')).not.toHaveProperty(
      INVOKING_SPAN_ATTR_KEY
    );
  });

  test('keeps the other keys of a caller-supplied weave object', async () => {
    const {traceId, spanId} = await userTracer().startActiveSpan(
      'user_work',
      async span => {
        await tracedOp('lookup', {weave: {tenant: 'acme'}})();
        span.end();
        return span.spanContext();
      }
    );

    // A caller's `weave` object replaces ours instead of merging with it, so
    // `client_version` and `source` are gone here. That predates this link.
    expect(await weaveAttributes('lookup')).toEqual({
      tenant: 'acme',
      [INVOKING_SPAN_ATTR_KEY]: {trace_id: traceId, span_id: spanId},
    });
  });
});
