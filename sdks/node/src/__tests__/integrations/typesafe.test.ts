import {AsyncLocalStorage} from 'async_hooks';
import {
  context,
  type Context,
  type ContextManager,
  ROOT_CONTEXT,
} from '@opentelemetry/api';
import {BasicTracerProvider} from '@opentelemetry/sdk-trace-base';
import {noul, TypeSafeClient, TypeSafeError} from '@typesafe-ai/sdk';

import {Conversation, getCurrentTurn, Turn} from '../../genai';
import {
  findSpan,
  setupExporterPerTest,
  setupGenAITestEnvironment,
} from '../genai/common';
import {
  instrumentTypeSafe,
  patchTypeSafeModule,
  wrapTypeSafe,
} from '../../integrations/typesafe';

const CAPTURE_ENV = 'OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT';
const SECRET = 'SECRET_BODY_xyz';
const PATCHED = Symbol.for('weave.typesafe.patched');

const questions = {
  billing: noul('Is this about billing?'),
};

function okBody(model = 'jev-1.13.0') {
  return {
    model,
    answers: {billing: {type: 'noul', noul: 0.91}},
    usage: {input_tokens: 11, output_tokens: 4},
  };
}

function jsonResponse(
  body: unknown,
  status = 200,
  requestId?: string
): Response {
  const headers = new Headers({'content-type': 'application/json'});
  if (requestId) {
    headers.set('x-typesafe-request-id', requestId);
  }
  return new Response(JSON.stringify(body), {status, headers});
}

function clientWith(fetch: TypeSafeClient['fetch'], retryMax = 0) {
  return new TypeSafeClient({
    apiKey: 'test-key',
    fetch,
    retry: {maxRetries: retryMax},
  });
}

function spanText(
  spans: {attributes: any; events: any[]; status: any}[]
): string {
  return JSON.stringify(
    spans.map(span => ({
      attributes: span.attributes,
      events: span.events,
      status: span.status,
    }))
  );
}

// `@opentelemetry/context-async-hooks` is not a dependency. Same stand-in as
// invokingSpan.test.ts, so an outer span is actually active.
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

describe('TypeSafe systemOne spans', () => {
  setupGenAITestEnvironment();
  const getExporter = setupExporterPerTest();
  const originalSystemOne = TypeSafeClient.prototype.systemOne;
  let previousCapture: string | undefined;

  beforeEach(() => {
    previousCapture = process.env[CAPTURE_ENV];
    delete process.env[CAPTURE_ENV];
  });

  afterEach(() => {
    TypeSafeClient.prototype.systemOne = originalSystemOne;
    delete (TypeSafeClient.prototype as any)[PATCHED];
    if (previousCapture === undefined) {
      delete process.env[CAPTURE_ENV];
    } else {
      process.env[CAPTURE_ENV] = previousCapture;
    }
  });

  function spans() {
    return getExporter().getFinishedSpans();
  }

  test('records one chat span under a synthetic turn', async () => {
    const fetch = jest.fn(async () => jsonResponse(okBody(), 200, 'req_123'));
    const client = wrapTypeSafe(clientWith(fetch));

    const promise = client.systemOne({
      state: 'I was charged twice.',
      questions,
    });
    const response = await promise.asResponse();
    const result = await promise;

    expect(client).toBe(wrapTypeSafe(client));
    expect(result.answers.billing.noul).toBe(0.91);
    expect(response.headers.get('x-typesafe-request-id')).toBe('req_123');
    expect(fetch).toHaveBeenCalledTimes(1);

    const chat = findSpan(spans(), 'chat jev-latest');
    const turn = findSpan(spans(), 'invoke_agent typesafe SDK');
    expect(chat.parentSpanId).toBe(turn.spanContext().spanId);
    expect(turn.parentSpanId).toBeUndefined();
    expect(chat.attributes['gen_ai.provider.name']).toBe('typesafe');
    expect(chat.attributes['gen_ai.request.model']).toBe('jev-latest');
    expect(chat.attributes['gen_ai.response.model']).toBe('jev-1.13.0');
    expect(chat.attributes['gen_ai.usage.input_tokens']).toBe(11);
    expect(chat.attributes['gen_ai.usage.output_tokens']).toBe(4);
    expect(chat.attributes['gen_ai.usage.total_tokens']).toBeUndefined();
    expect(chat.attributes['gen_ai.response.id']).toBe('req_123');
    expect(chat.attributes['gen_ai.output.type']).toBe('json');
    expect(chat.attributes['weave.integration.name']).toBe('typesafe');
    expect(chat.attributes['weave.integration.meta.package_name']).toBe(
      'typesafe-sdk'
    );
    expect(chat.attributes['weave.integration.operation']).toBe(
      'typesafe.system_one'
    );
    expect(turn.attributes['gen_ai.provider.name']).toBeUndefined();
    expect(turn.attributes['weave.integration.operation']).toBe(
      'typesafe.system_one'
    );
    expect(
      JSON.parse(String(chat.attributes['gen_ai.input.messages']))
    ).toEqual([{role: 'user', content: 'I was charged twice.'}]);
    expect(
      JSON.parse(String(chat.attributes['gen_ai.output.messages']))
    ).toEqual([
      {
        role: 'assistant',
        parts: [
          {type: 'text', content: '{"billing":{"noul":0.91,"type":"noul"}}'},
        ],
      },
    ]);
    expect(JSON.parse(String(chat.attributes['typesafe.questions']))).toEqual([
      {id: 'billing', type: 'noul', instructions: 'Is this about billing?'},
    ]);
    expect(getCurrentTurn()).toBeUndefined();
  });

  test('stores array state as a text part', async () => {
    const client = wrapTypeSafe(
      clientWith(async () => jsonResponse(okBody(), 200, 'req_123'))
    );
    await client.systemOne({
      state: ['a', 'b'],
      questions,
      model: 'jev-preview',
    });
    const chat = findSpan(spans(), 'chat jev-preview');
    const input = JSON.parse(String(chat.attributes['gen_ai.input.messages']));
    expect(input).toEqual([
      {role: 'user', parts: [{type: 'text', content: '["a","b"]'}]},
    ]);
    expect(input[0].content).toBeUndefined();
  });

  test('env false drops content and a client option overrides it', async () => {
    process.env[CAPTURE_ENV] = 'false';
    const off = wrapTypeSafe(
      clientWith(async () => jsonResponse(okBody(), 200, 'req_123'))
    );
    await off.systemOne({state: SECRET, questions});
    const hidden = findSpan(spans(), 'chat jev-latest');
    expect(hidden.attributes['gen_ai.input.messages']).toBeUndefined();
    expect(hidden.attributes['gen_ai.output.messages']).toBeUndefined();
    expect(hidden.attributes['typesafe.questions']).toBeUndefined();
    expect(hidden.attributes['gen_ai.usage.input_tokens']).toBe(11);
    expect(spanText([hidden])).not.toContain(SECRET);

    getExporter().reset();
    const on = wrapTypeSafe(
      clientWith(async () => jsonResponse(okBody(), 200, 'req_123')),
      {captureContent: true}
    );
    await on.systemOne({state: 'visible', questions});
    const shown = findSpan(spans(), 'chat jev-latest');
    expect(
      JSON.parse(String(shown.attributes['gen_ai.input.messages']))
    ).toEqual([{role: 'user', content: 'visible'}]);
  });

  test('a later wrap updates capture for the same client', async () => {
    const client = wrapTypeSafe(clientWith(async () => jsonResponse(okBody())));
    wrapTypeSafe(client, {captureContent: false});
    await client.systemOne({state: SECRET, questions, model: 'jev-latest'});
    const chat = findSpan(spans(), 'chat jev-latest');
    expect(chat.attributes['gen_ai.input.messages']).toBeUndefined();
    expect(spanText([chat])).not.toContain(SECRET);
    expect(spans().filter(span => span.name.startsWith('chat'))).toHaveLength(
      1
    );
  });

  test('a native turn is the parent', async () => {
    const turn = Turn.create({agentName: 'app'});
    const client = wrapTypeSafe(
      clientWith(async () => jsonResponse(okBody(), 200, 'req_123'))
    );
    await client.systemOne({state: 'hello', questions, model: 'jev-latest'});
    turn.end();

    const chat = findSpan(spans(), 'chat jev-latest');
    const parent = findSpan(spans(), 'invoke_agent app');
    expect(chat.parentSpanId).toBe(parent.spanContext().spanId);
    expect(
      spans().some(span => span.name === 'invoke_agent typesafe SDK')
    ).toBe(false);
    expect(parent.attributes['weave.integration.operation']).toBeUndefined();
  });

  test('a date in state is stored as its json text', async () => {
    const client = wrapTypeSafe(clientWith(async () => jsonResponse(okBody())));
    await client.systemOne({
      state: {when: new Date('2026-01-02T00:00:00.000Z')} as any,
      questions,
      model: 'jev-latest',
    });
    const input = JSON.parse(
      String(
        findSpan(spans(), 'chat jev-latest').attributes['gen_ai.input.messages']
      )
    );
    expect(input).toEqual([
      {
        role: 'user',
        parts: [{type: 'text', content: '{"when":"2026-01-02T00:00:00.000Z"}'}],
      },
    ]);
  });

  test('an unencodable state does not open a turn', async () => {
    const fetch = jest.fn(async () => jsonResponse(okBody()));
    const client = wrapTypeSafe(clientWith(fetch));
    await expect(
      client.systemOne({state: {n: BigInt(1)} as any, questions})
    ).rejects.toThrow(TypeError);
    expect(spans()).toHaveLength(0);
    expect(fetch).toHaveBeenCalledTimes(0);
  });

  test('a conversation without a turn keeps its id', async () => {
    const conversation = Conversation.create({
      conversationId: 'c-1',
      agentName: 'app',
      agentId: 'app-prod',
      agentDescription: 'The app agent',
      agentVersion: '9.9.9',
      model: 'not-the-typesafe-model',
      attributes: {'customer.tier': 'gold'},
    });
    const client = wrapTypeSafe(clientWith(async () => jsonResponse(okBody())));
    await client.systemOne({state: 'hello', questions, model: 'jev-latest'});
    conversation.end();
    const chat = findSpan(spans(), 'chat jev-latest');
    const turn = findSpan(spans(), 'invoke_agent typesafe SDK');
    expect(chat.parentSpanId).toBe(turn.spanContext().spanId);
    expect(turn.attributes['gen_ai.conversation.id']).toBe('c-1');
    expect(chat.attributes['gen_ai.conversation.id']).toBe('c-1');
    expect(turn.attributes['customer.tier']).toBe('gold');
    expect(chat.attributes['customer.tier']).toBe('gold');
    expect(turn.attributes['gen_ai.agent.name']).toBe('typesafe SDK');
    expect(turn.attributes['gen_ai.agent.id']).toBeUndefined();
    expect(turn.attributes['gen_ai.agent.description']).toBeUndefined();
    expect(turn.attributes['gen_ai.agent.version']).toBeUndefined();
    expect(turn.attributes['gen_ai.request.model']).toBeUndefined();
    expect(spans().some(span => span.name === 'invoke_agent app')).toBe(false);
    expect(getCurrentTurn()).toBeUndefined();
  });

  test('an outer span does not replace the synthetic turn', async () => {
    context.setGlobalContextManager(new TestContextManager());
    try {
      const outerTracer = new BasicTracerProvider().getTracer('test');
      const client = wrapTypeSafe(
        clientWith(async () => jsonResponse(okBody()))
      );
      let outerId = '';
      await outerTracer.startActiveSpan('outer', async span => {
        outerId = span.spanContext().spanId;
        await client.systemOne({
          state: 'hello',
          questions,
          model: 'jev-latest',
        });
        const child = outerTracer.startSpan('child');
        expect((child as any).parentSpanId).toBe(outerId);
        child.end();
        span.end();
      });
      const chat = findSpan(spans(), 'chat jev-latest');
      const turn = findSpan(spans(), 'invoke_agent typesafe SDK');
      expect(chat.parentSpanId).toBe(turn.spanContext().spanId);
      expect(turn.parentSpanId).toBeUndefined();
    } finally {
      context.disable();
    }
  });

  test('http errors do not copy the response body onto the span', async () => {
    const client = wrapTypeSafe(
      clientWith(async () => jsonResponse({error: SECRET}, 400, 'req_err'))
    );
    await expect(
      client.systemOne({state: 'hello', questions, model: 'jev-latest'})
    ).rejects.toMatchObject({status: 400});

    const chat = findSpan(spans(), 'chat jev-latest');
    const turn = findSpan(spans(), 'invoke_agent typesafe SDK');
    expect(spanText(spans())).not.toContain(SECRET);
    expect(chat.status.code).toBe(2);
    expect(chat.status.message).toBeFalsy();
    expect(chat.attributes['http.response.status_code']).toBe(400);
    expect(chat.attributes['gen_ai.response.id']).toBe('req_err');
    expect(chat.attributes['error.type']).toBe('BadRequestError');
    expect(turn.attributes['error.type']).toBe('BadRequestError');
    expect(chat.attributes['gen_ai.output.messages']).toBeUndefined();
  });

  test('a user turn is left for the caller to finish', async () => {
    const turn = Turn.create({agentName: 'app'});
    const client = wrapTypeSafe(
      clientWith(async () => jsonResponse({error: SECRET}, 400, 'req_err'))
    );
    await expect(client.systemOne({state: 'hello', questions})).rejects.toThrow(
      TypeSafeError
    );
    turn.end();

    const chat = findSpan(spans(), 'chat jev-latest');
    const parent = findSpan(spans(), 'invoke_agent app');
    expect(spanText([chat, parent])).not.toContain(SECRET);
    expect(chat.attributes['error.type']).toBe('BadRequestError');
    expect(parent.attributes['error.type']).toBeUndefined();
    expect(parent.status.code).not.toBe(2);
  });

  test('a missing request id is omitted', async () => {
    const client = wrapTypeSafe(
      clientWith(async () => jsonResponse(okBody(), 200))
    );
    await client.systemOne({state: 'hello', questions, model: 'jev-latest'});
    expect(
      findSpan(spans(), 'chat jev-latest').attributes['gen_ai.response.id']
    ).toBeUndefined();
  });

  test('validation errors are rethrown without their text on the span', async () => {
    const client = wrapTypeSafe(clientWith(async () => jsonResponse(okBody())));
    let error: unknown;
    try {
      await client.systemOne({state: 'hello', questions: {}});
    } catch (caught) {
      error = caught;
    }
    expect(error).toBeInstanceOf(TypeSafeError);
    expect(String(error)).toContain('At least one question is required.');
    const chat = findSpan(spans(), 'chat jev-latest');
    expect(spanText([chat])).not.toContain(
      'At least one question is required.'
    );
    expect(chat.attributes['error.type']).toBe('TypeSafeError');
    expect(chat.status.message).toBeFalsy();
  });

  test('models.list is not a chat span', async () => {
    const fetch = jest.fn(async () =>
      jsonResponse({
        models: [
          {name: 'jev-latest', description: '', release_date: '2026-01-01'},
        ],
      })
    );
    const client = wrapTypeSafe(clientWith(fetch));
    await expect(client.models.list()).resolves.toHaveLength(1);
    expect(spans().some(span => span.name.startsWith('chat'))).toBe(false);
  });

  test('retries become one span and the failed body stays off it', async () => {
    const fetch = jest
      .fn()
      .mockResolvedValueOnce(jsonResponse({error: SECRET}, 500, 'req_retry'))
      .mockResolvedValueOnce(jsonResponse(okBody(), 200, 'req_ok'));
    const client = wrapTypeSafe(clientWith(fetch, 1));
    await client.systemOne({state: 'hello', questions, model: 'jev-latest'});
    expect(fetch).toHaveBeenCalledTimes(2);
    const chats = spans().filter(span => span.name.startsWith('chat'));
    expect(chats).toHaveLength(1);
    expect(spanText(spans())).not.toContain(SECRET);
    expect(chats[0].attributes['gen_ai.response.id']).toBe('req_ok');
  });

  test('map does not run until the span is written', async () => {
    const client = wrapTypeSafe(
      clientWith(async () => jsonResponse(okBody(), 200, 'req_123'))
    );
    let called = false;
    const mapped = client
      .systemOne({state: 'hello', questions, model: 'jev-latest'})
      .map(data => {
        called = true;
        expect(spans().some(span => span.name === 'chat jev-latest')).toBe(
          true
        );
        return data.model;
      });
    expect(called).toBe(false);
    await expect(mapped).resolves.toBe('jev-1.13.0');
    expect(called).toBe(true);
  });

  test('parallel calls get separate turns', async () => {
    const client = wrapTypeSafe(
      clientWith(async (_url, init) => {
        const body = JSON.parse(String(init?.body));
        return jsonResponse(okBody(body.model), 200, body.model);
      })
    );
    await Promise.all([
      client.systemOne({state: 'one', questions, model: 'jev-latest'}),
      client.systemOne({state: 'two', questions, model: 'jev-preview'}),
    ]);
    const turns = spans().filter(
      span => span.name === 'invoke_agent typesafe SDK'
    );
    const chats = spans().filter(span => span.name.startsWith('chat '));
    expect(turns).toHaveLength(2);
    expect(chats).toHaveLength(2);
    expect(new Set(chats.map(span => span.parentSpanId))).toEqual(
      new Set(turns.map(span => span.spanContext().spanId))
    );
  });

  test('the module hook patches the prototype once', async () => {
    const sdk = await import('@typesafe-ai/sdk');
    patchTypeSafeModule(sdk);
    patchTypeSafeModule(sdk);
    const client = clientWith(async () => jsonResponse(okBody()));
    await client.systemOne({state: 'hello', questions, model: 'jev-latest'});
    expect(spans().filter(span => span.name.startsWith('chat'))).toHaveLength(
      1
    );

    getExporter().reset();
    const wrapped = wrapTypeSafe(client);
    expect(wrapped).toBe(client);
    await client.systemOne({state: 'hello', questions, model: 'jev-latest'});
    expect(spans().filter(span => span.name.startsWith('chat'))).toHaveLength(
      1
    );
  });

  test('an instance patch shadows a later prototype patch', async () => {
    const client = wrapTypeSafe(clientWith(async () => jsonResponse(okBody())));
    patchTypeSafeModule(await import('@typesafe-ai/sdk'));
    await client.systemOne({state: 'hello', questions, model: 'jev-latest'});
    expect(spans().filter(span => span.name.startsWith('chat'))).toHaveLength(
      1
    );
  });

  test('instrumentTypeSafe can be called before the SDK exists in a bundle', () => {
    expect(() => {
      instrumentTypeSafe();
      instrumentTypeSafe();
    }).not.toThrow();
  });
});
