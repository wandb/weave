import OpenAI from 'openai';
import {InMemoryTraceServer} from '../helpers/inMemoryTraceServer';
import {wrapOpenAI} from '../../integrations/openai';
import {initWithCustomTraceServer} from '../clientMock';

// Every other OpenAI test hand-builds its client shape, so nothing checks the
// proxy against the SDK we ship against — which is how tracing for
// `chat.completions.parse` went quiet when openai-node v5 moved it out of
// `beta.chat`.
describe('wrapOpenAI against the installed openai package', () => {
  let traceServer: InMemoryTraceServer;
  const testProjectName = 'test-project';

  beforeEach(() => {
    traceServer = new InMemoryTraceServer();
    initWithCustomTraceServer(testProjectName, traceServer);
  });

  test('still finds every method it intercepts', () => {
    const client = new OpenAI({apiKey: 'test-key'});
    // Capture from the same instance the wrapper gets, so this keeps working if
    // the SDK ever moves these off the resource prototypes.
    const raw = {
      create: client.chat.completions.create,
      parse: client.chat.completions.parse,
      generate: client.images.generate,
      responsesCreate: client.responses.create,
    };
    const wrapped = wrapOpenAI(client);

    expect(wrapped.chat.completions.create).not.toBe(raw.create);
    expect(wrapped.chat.completions.parse).not.toBe(raw.parse);
    expect(wrapped.images.generate).not.toBe(raw.generate);
    expect(wrapped.responses.create).not.toBe(raw.responsesCreate);
  });

  test('logs one call for one parse', async () => {
    const client = new OpenAI({
      apiKey: 'test-key',
      fetch: async () =>
        new Response(
          JSON.stringify({
            id: 'chatcmpl-1',
            object: 'chat.completion',
            created: 1,
            model: 'gpt-4o-2024-05-13',
            choices: [
              {
                index: 0,
                message: {
                  role: 'assistant',
                  content: '{"city":"Paris"}',
                  refusal: null,
                },
                logprobs: null,
                finish_reason: 'stop',
              },
            ],
            usage: {prompt_tokens: 4, completion_tokens: 6, total_tokens: 10},
          }),
          {status: 200, headers: {'content-type': 'application/json'}}
        ),
    });

    const result = await wrapOpenAI(client).chat.completions.parse({
      model: 'gpt-4o-2024-05-13',
      messages: [{role: 'user', content: 'Which city?'}],
      response_format: {
        type: 'json_schema',
        json_schema: {name: 'city', schema: {type: 'object'}},
      },
    });
    expect(result.choices[0].message.parsed).toEqual({city: 'Paris'});

    await new Promise(resolve => setTimeout(resolve, 300));

    // `parse` runs `create` internally, so a wrapped `create` reachable from
    // there — or a patch applied to the resource in place — would show up as a
    // second call.
    const calls = await traceServer.getCalls(testProjectName);
    expect(calls).toHaveLength(1);
    expect(calls[0].op_name).toContain('openai.chat.completions.parse');
    // Weave's transform composes after the SDK's, so the trace carries the
    // deserialized object rather than only the raw JSON string.
    expect(calls[0].output.choices[0].message.parsed).toEqual({city: 'Paris'});
    expect(calls[0].summary).toEqual({
      usage: {
        'gpt-4o-2024-05-13': {
          requests: 1,
          prompt_tokens: 4,
          completion_tokens: 6,
          total_tokens: 10,
        },
      },
    });
  });

  test('records the responses resource as a type marker', async () => {
    const apiKey = 'not-a-real-key';
    const client = new OpenAI({
      apiKey,
      fetch: async () =>
        new Response(
          JSON.stringify({
            id: 'resp_1',
            object: 'response',
            created_at: 1,
            model: 'gpt-4o-2024-05-13',
            status: 'completed',
            output: [],
            usage: {input_tokens: 4, output_tokens: 2, total_tokens: 6},
          }),
          {status: 200, headers: {'content-type': 'application/json'}}
        ),
    });

    await wrapOpenAI(client).responses.create({
      model: 'gpt-4o-2024-05-13',
      input: 'Which city?',
    });

    const calls = await traceServer.getCalls(testProjectName);
    expect(calls).toHaveLength(1);
    // A string for `self` keeps the app's Responses chat view matching the
    // call, which needs `self` present; nothing reads its contents.
    expect(calls[0].inputs).toEqual({
      self: '<Responses>',
      model: 'gpt-4o-2024-05-13',
      input: 'Which city?',
    });
    expect(JSON.stringify(calls[0])).not.toContain(apiKey);
  });
});
