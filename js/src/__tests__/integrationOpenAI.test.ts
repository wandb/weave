import { initWithCustomTraceServer } from '../clientApi';
import { InMemoryTraceServer } from '../inMemoryTraceServer';
import { makeMockOpenAIChat } from './openaiMock';
import { makeOpenAIChatCompletionsOp, wrapOpenAI } from '../integrations/openai';

// Helper function to get calls
async function getCalls(traceServer: InMemoryTraceServer, projectId: string) {
    const calls = await traceServer.calls.callsStreamQueryPost({
        project_id: projectId,
        limit: 100,
    }).then(result => result.calls);
    return calls;
}

const wait = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

describe('OpenAI Integration', () => {
    let inMemoryTraceServer: InMemoryTraceServer;
    const testProjectName = 'test-project';
    let mockOpenAI: any;
    let patchedOpenAI: any;

    beforeEach(() => {
        inMemoryTraceServer = new InMemoryTraceServer();
        initWithCustomTraceServer(testProjectName, inMemoryTraceServer);

        const mockOpenAIChat = makeMockOpenAIChat((messages) => ({
            content: messages[messages.length - 1].content.toUpperCase(),
            functionCalls: []
        }));

        mockOpenAI = { chat: { completions: { create: mockOpenAIChat } } };
        patchedOpenAI = wrapOpenAI();
        patchedOpenAI.chat.completions.create = makeOpenAIChatCompletionsOp(mockOpenAIChat);
    });

    test('non-streaming chat completion', async () => {
        const messages = [{ role: 'user', content: 'Hello, AI!' }];

        // Direct API call
        const directResult = await mockOpenAI.chat.completions.create({ messages });

        // Op-wrapped API call
        const opResult = await patchedOpenAI.chat.completions.create({ messages });

        // Wait for any pending batch processing
        await wait(300);

        // Check results
        expect(opResult).toMatchObject({
            object: directResult.object,
            model: directResult.model,
            choices: directResult.choices,
            usage: directResult.usage,
        });
        expect(opResult.id).toMatch(/^chatcmpl-/);
        expect(opResult.system_fingerprint).toMatch(/^fp_/);
        expect(opResult.created).toBeCloseTo(directResult.created, -2); // Allow 1 second difference
        expect(opResult.choices[0].message.content).toBe('HELLO, AI!');

        // Check logged Call values
        const calls = await getCalls(inMemoryTraceServer, testProjectName);
        expect(calls).toHaveLength(1);
        expect(calls[0].op_name).toBe('openai.chat.completions.create');
        expect(calls[0].inputs).toEqual({ arg0: { messages } });
        expect(calls[0].output).toMatchObject({
            object: opResult.object,
            model: opResult.model,
            choices: opResult.choices,
            usage: opResult.usage,
        });
        expect(calls[0].output.id).toMatch(/^chatcmpl-/);
        expect(calls[0].output.system_fingerprint).toMatch(/^fp_/);
        expect(calls[0].output.created).toBeCloseTo(opResult.created, -2);
        expect(calls[0].summary).toEqual({
            usage: {
                'gpt-4o-2024-05-13': {
                    requests: 1,
                    prompt_tokens: 2,
                    completion_tokens: 2,
                    total_tokens: 4
                }
            }
        });
        // Ensure stream_options is not present in the logged call for non-streaming requests
        expect(calls[0].inputs.arg0).not.toHaveProperty('stream_options');
    });

    test('streaming chat completion basic', async () => {
        const messages = [{ role: 'user', content: 'Hello, streaming AI!' }];

        // Direct API call
        const directStream = await mockOpenAI.chat.completions.create({ messages, stream: true });
        let directContent = '';
        for await (const chunk of directStream) {
            if (chunk.choices && chunk.choices[0]?.delta?.content) {
                directContent += chunk.choices[0].delta.content;
            }
        }

        // Op-wrapped API call
        const opStream = await patchedOpenAI.chat.completions.create({ messages, stream: true });
        let opContent = '';
        let usageChunkSeen = false;
        for await (const chunk of opStream) {
            if (chunk.choices && chunk.choices[0]?.delta?.content) {
                opContent += chunk.choices[0].delta.content;
            }
            if ('usage' in chunk) {
                usageChunkSeen = true;
            }
        }

        // Wait for any pending batch processing
        await wait(300);

        // Check results
        expect(opContent).toBe(directContent);
        expect(opContent).toBe('HELLO, STREAMING AI!');

        // TOOD: this is broken still!
        // expect(usageChunkSeen).toBe(false);  // Ensure no usage chunk is seen in the user-facing stream

        // Check logged Call values
        const calls = await getCalls(inMemoryTraceServer, testProjectName);
        expect(calls).toHaveLength(1);
        expect(calls[0].op_name).toBe('openai.chat.completions.create');
        expect(calls[0].inputs).toEqual({ arg0: { messages, stream: true } });
        expect(calls[0].output).toMatchObject({
            choices: [{
                message: {
                    content: 'HELLO, STREAMING AI!'
                }
            }]
        });
        expect(calls[0].summary).toEqual({
            usage: {
                'gpt-4o-2024-05-13': {
                    requests: 1,
                    prompt_tokens: 3,
                    completion_tokens: 3,
                    total_tokens: 6
                }
            }
        });
    });

    // Add a new test for streaming with explicit usage request
    test('streaming chat completion with explicit usage request', async () => {
        const messages = [{ role: 'user', content: 'Hello, streaming AI with usage!' }];

        // Op-wrapped API call with explicit usage request
        const opStream = await patchedOpenAI.chat.completions.create({
            messages,
            stream: true,
            stream_options: { include_usage: true }
        });
        let opContent = '';
        let usageChunkSeen = false;
        for await (const chunk of opStream) {
            if (chunk.choices[0]?.delta?.content) {
                opContent += chunk.choices[0].delta.content;
            }
            if ('usage' in chunk) {
                usageChunkSeen = true;
            }
        }

        // Wait for any pending batch processing
        await wait(300);

        // Check results
        expect(opContent).toBe('HELLO, STREAMING AI WITH USAGE!');
        expect(usageChunkSeen).toBe(true);  // Ensure usage chunk is seen when explicitly requested

        // Check logged Call values
        const calls = await getCalls(inMemoryTraceServer, testProjectName);
        expect(calls).toHaveLength(1);
        expect(calls[0].summary).toEqual({
            usage: {
                'gpt-4o-2024-05-13': {
                    requests: 1,
                    prompt_tokens: 5,
                    completion_tokens: 5,
                    total_tokens: 10
                }
            }
        });
    });

    test('chat completion with function call', async () => {
        const messages = [{ role: 'user', content: 'What\'s the weather in London?' }];
        const functions = [{
            name: 'get_weather',
            description: 'Get the weather in a location',
            parameters: {
                type: 'object',
                properties: {
                    location: { type: 'string' }
                },
                required: ['location']
            }
        }];

        // Update mock to include function call
        const mockOpenAIChat = makeMockOpenAIChat(() => ({
            content: '',
            functionCalls: [{
                name: 'get_weather',
                arguments: { location: 'London' }
            }]
        }));
        mockOpenAI.chat.completions.create = mockOpenAIChat;
        patchedOpenAI.chat.completions.create = makeOpenAIChatCompletionsOp(mockOpenAIChat);

        // Direct API call
        const directResult = await mockOpenAI.chat.completions.create({ messages, functions });

        // Op-wrapped API call
        const opResult = await patchedOpenAI.chat.completions.create({ messages, functions });

        // Wait for any pending batch processing
        await wait(300);

        // Check results
        expect(opResult).toMatchObject({
            object: directResult.object,
            model: directResult.model,
            choices: directResult.choices,
            usage: directResult.usage,
        });
        expect(opResult.id).toMatch(/^chatcmpl-/);
        expect(opResult.system_fingerprint).toMatch(/^fp_/);
        expect(opResult.created).toBeCloseTo(directResult.created, -2); // Allow 1 second difference
        expect(opResult.choices[0].message.function_call).toEqual({
            name: 'get_weather',
            arguments: '{"location":"London"}'
        });

        // Check logged Call values
        const calls = await getCalls(inMemoryTraceServer, testProjectName);
        expect(calls).toHaveLength(1);
        expect(calls[0].op_name).toBe('openai.chat.completions.create');
        expect(calls[0].inputs).toEqual({ arg0: { messages, functions } });
        expect(calls[0].output).toMatchObject({
            object: opResult.object,
            model: opResult.model,
            choices: opResult.choices,
            usage: opResult.usage,
        });
        expect(calls[0].output.id).toMatch(/^chatcmpl-/);
        expect(calls[0].output.system_fingerprint).toMatch(/^fp_/);
        expect(calls[0].output.created).toBeCloseTo(opResult.created, -2);
        expect(calls[0].summary).toEqual({
            usage: {
                'gpt-4o-2024-05-13': {
                    requests: 1,
                    prompt_tokens: 5,
                    completion_tokens: 3,
                    total_tokens: 8
                }
            }
        });
    });
});