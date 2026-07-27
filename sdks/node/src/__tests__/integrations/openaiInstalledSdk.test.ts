import OpenAI from 'openai';
import {InMemoryTraceServer} from '../helpers/inMemoryTraceServer';
import {wrapOpenAI} from '../../integrations/openai';
import {initWithCustomTraceServer} from '../clientMock';

// Every other OpenAI test hand-builds its client shape, so nothing checks the
// proxy against the SDK we ship against — which is how tracing for
// `chat.completions.parse` went quiet when openai-node v5 moved it out of
// `beta.chat`.
describe('wrapOpenAI against the installed openai package', () => {
  const testProjectName = 'test-project';

  test('still wraps every method it intercepts', () => {
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
    const traceServer = new InMemoryTraceServer();
    initWithCustomTraceServer(testProjectName, traceServer);

    let httpRequests = 0;
    const client = new OpenAI({
      apiKey: 'test-key',
      fetch: async () => {
        httpRequests += 1;
        return new Response(
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
        );
      },
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

    // `parse` runs `create` internally. It reaches it through the SDK's own raw
    // client reference, so only the outer call is traced — a second call here
    // would mean the internal one found a wrapped `create`.
    const calls = await traceServer.getCalls(testProjectName);
    expect(calls).toHaveLength(1);
    expect(calls[0].op_name).toContain('openai.chat.completions.parse');
    expect(httpRequests).toBe(1);
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
});
