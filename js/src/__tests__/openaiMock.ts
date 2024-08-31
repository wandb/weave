import { op } from '../clientApi';

function generateId() {
    return "chatcmpl-" + Math.random().toString(36).substr(2, 9);
}

function generateSystemFingerprint() {
    return "fp_" + Math.random().toString(36).substr(2, 9);
}

type FunctionCall = {
    name: string;
    arguments: string;
};

type ResponseFn = (messages: any[]) => {
    content: string;
    functionCalls?: FunctionCall[];
};

// Simple function to estimate token count
function estimateTokenCount(text: string): number {
    return Math.ceil(text.split(/\s+/).length);  // 1 token per word for testing
}

export function makeMockOpenAIChat(responseFn: ResponseFn) {
    return function openaiChatCompletionsCreate({
        messages,
        stream = false,
        model = "gpt-4o-2024-05-13",
        ...otherOptions
    }: {
        messages: any[];
        stream?: boolean;
        model?: string;
        [key: string]: any;
    }) {
        const response = responseFn(messages);
        const { content, functionCalls = [] } = response;

        const promptTokens = messages.reduce((acc, msg) => acc + estimateTokenCount(msg.content), 0);
        const completionTokens = estimateTokenCount(content) +
            functionCalls.reduce((acc, fc) => acc + estimateTokenCount(fc.name) + estimateTokenCount(fc.arguments), 0);
        const totalTokens = promptTokens + completionTokens;

        if (stream) {
            return {
                [Symbol.asyncIterator]: async function* () {
                    yield* generateChunks(content, functionCalls, model, promptTokens, completionTokens, totalTokens);
                }
            };
        } else {
            return {
                id: generateId(),
                object: "chat.completion",
                created: Math.floor(Date.now() / 1000),
                model: model,
                choices: [{
                    index: 0,
                    message: {
                        role: "assistant",
                        content: content,
                        function_call: functionCalls[0] || null,
                        refusal: null
                    },
                    logprobs: null,
                    finish_reason: functionCalls.length > 0 ? "function_call" : "stop"
                }],
                usage: {
                    prompt_tokens: promptTokens,
                    completion_tokens: completionTokens,
                    total_tokens: totalTokens
                },
                system_fingerprint: generateSystemFingerprint()
            };
        }
    };
}

function* generateChunks(
    content: string,
    functionCalls: FunctionCall[],
    model: string,
    promptTokens: number,
    completionTokens: number,
    totalTokens: number
) {
    const id = generateId();
    const systemFingerprint = generateSystemFingerprint();
    const created = Math.floor(Date.now() / 1000);

    // Initial chunk
    yield {
        id,
        object: "chat.completion.chunk",
        created,
        model,
        system_fingerprint: systemFingerprint,
        choices: [{
            index: 0,
            delta: { role: "assistant", content: "", refusal: null },
            logprobs: null,
            finish_reason: null
        }]
    };

    // Content chunks
    for (const word of content.split(' ')) {
        yield {
            id,
            object: "chat.completion.chunk",
            created,
            model,
            system_fingerprint: systemFingerprint,
            choices: [{
                index: 0,
                delta: { content: word + ' ' },
                logprobs: null,
                finish_reason: null
            }]
        };
    }

    // Function call chunks
    for (const functionCall of functionCalls) {
        yield {
            id,
            object: "chat.completion.chunk",
            created,
            model,
            system_fingerprint: systemFingerprint,
            choices: [{
                index: 0,
                delta: { function_call: { name: functionCall.name, arguments: "" } },
                logprobs: null,
                finish_reason: null
            }]
        };

        const args = functionCall.arguments;
        for (let i = 0; i < args.length; i += 10) {
            yield {
                id,
                object: "chat.completion.chunk",
                created,
                model,
                system_fingerprint: systemFingerprint,
                choices: [{
                    index: 0,
                    delta: { function_call: { arguments: args.slice(i, i + 10) } },
                    logprobs: null,
                    finish_reason: null
                }]
            };
        }
    }

    // Final chunk with usage information
    yield {
        id,
        object: "chat.completion.chunk",
        created,
        model,
        system_fingerprint: systemFingerprint,
        choices: [{
            index: 0,
            delta: {},
            logprobs: null,
            finish_reason: functionCalls.length > 0 ? "function_call" : "stop"
        }],
        usage: {
            prompt_tokens: promptTokens,
            completion_tokens: completionTokens,
            total_tokens: totalTokens
        }
    };
}