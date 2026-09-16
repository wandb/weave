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

import {requireGlobalClient} from '../clientApi';
import {INVOKING_SPAN_ATTR_KEY} from '../constants';
import {op} from '../op';
import {packageVersion} from '../utils/packageVersion';
import {initWithCustomTraceServer} from './clientMock';
import {TEST_PROJECT} from './genai/common';
import {type Call, InMemoryTraceServer} from './helpers/inMemoryTraceServer';

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

/** Everything a call carries under `weave` when no link was recorded. */
const WITHOUT_LINK = {client_version: packageVersion, source: 'js-sdk'};

// Every test goes through the public path — run an op, read the stored call —
// because the span has to be read before `createCall` awaits, which a direct
// call to the resolver cannot show.
describe('invoking span', () => {
  let traceServer: InMemoryTraceServer;

  beforeEach(() => {
    traceServer = new InMemoryTraceServer();
    initWithCustomTraceServer(TEST_PROJECT, traceServer);
    context.setGlobalContextManager(new TestContextManager());
  });

  afterEach(() => {
    // setGlobalContextManager refuses to overwrite an existing registration, so
    // every test after the first would silently keep this one.
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
    // Query directly once the client has drained: getCalls() waits for the call
    // count to move, so after a flush it burns its full 1500ms timeout and logs
    // a warning.
    await requireGlobalClient().flush();
    const calls = traceServer.listCalls(TEST_PROJECT);
    const call = calls.find((c: Call) => c.op_name.includes(opName));
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

    // Spelled out, not via the constant: Python matches on this string, so a
    // rename has to fail here rather than pass every test that imports it.
    expect(await weaveAttributes('lookup')).toEqual({
      client_version: packageVersion,
      source: 'js-sdk',
      invoking_span: {trace_id: traceId, span_id: spanId},
    });
  });

  test('records nothing outside a span', async () => {
    await tracedOp('lookup')();

    expect(await weaveAttributes('lookup')).toEqual(WITHOUT_LINK);
  });

  test('records nothing for a span that will not be exported', async () => {
    const tracer = userTracer({sampler: recordOnlySampler});
    await tracer.startActiveSpan('user_work', async span => {
      await tracedOp('lookup')();
      span.end();
    });

    expect(await weaveAttributes('lookup')).toEqual(WITHOUT_LINK);
  });

  test('records nothing for a span that has already ended', async () => {
    await userTracer().startActiveSpan('user_work', async span => {
      span.end();
      await tracedOp('lookup')();
    });

    expect(await weaveAttributes('lookup')).toEqual(WITHOUT_LINK);
  });

  test('records nothing for an all-zero span identity', async () => {
    const tracer = userTracer({idGenerator: zeroIdGenerator});
    await tracer.startActiveSpan('user_work', async span => {
      await tracedOp('lookup')();
      span.end();
    });

    expect(await weaveAttributes('lookup')).toEqual(WITHOUT_LINK);
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

  test('records a span the op body ends while the call start is in flight', async () => {
    // `createCall` suspends on its first await and hands control back, so the
    // op body runs — and ends the span — before it reaches the attributes. Read
    // the span there instead of on entry and this is the case that goes silent.
    await userTracer().startActiveSpan('user_work', async span => {
      await op(async () => span.end(), {name: 'ends_span'})();
    });

    expect(await weaveAttributes('ends_span')).toHaveProperty(
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
    // Empty, not `WITHOUT_LINK`: the supplied object replaced ours, and all it
    // held was the key we drop.
    expect(await weaveAttributes('outside')).toEqual({});
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

    // A caller's `weave` object replaces ours instead of merging, so
    // `client_version` and `source` are gone here — that predates this link.
    expect(await weaveAttributes('lookup')).toEqual({
      tenant: 'acme',
      [INVOKING_SPAN_ATTR_KEY]: {trace_id: traceId, span_id: spanId},
    });
  });
});
