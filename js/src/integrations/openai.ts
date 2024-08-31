import OpenAI from 'openai';
import { op } from '../clientApi';

function aggregateOpenAIStream(stream: AsyncIterable<any>): Promise<any> {
    return new Promise(async (resolve, reject) => {
        let aggregatedResponse: any = {
            id: '',
            object: 'chat.completion',
            created: 0,
            model: '',
            choices: [{
                index: 0,
                message: {
                    role: 'assistant',
                    content: '',
                    function_call: null,
                },
                finish_reason: null,
            }],
            usage: null,
        };

        try {
            for await (const chunk of stream) {
                if (chunk.id) aggregatedResponse.id = chunk.id;
                if (chunk.object) aggregatedResponse.object = chunk.object;
                if (chunk.created) aggregatedResponse.created = chunk.created;
                if (chunk.model) aggregatedResponse.model = chunk.model;

                if (chunk.choices && chunk.choices.length > 0) {
                    const choice = chunk.choices[0];
                    if (choice.delta) {
                        if (choice.delta.role) {
                            aggregatedResponse.choices[0].message.role = choice.delta.role;
                        }
                        if (choice.delta.content) {
                            aggregatedResponse.choices[0].message.content += choice.delta.content;
                        }
                        if (choice.delta.function_call) {
                            if (!aggregatedResponse.choices[0].message.function_call) {
                                aggregatedResponse.choices[0].message.function_call = { name: '', arguments: '' };
                            }
                            if (choice.delta.function_call.name) {
                                aggregatedResponse.choices[0].message.function_call.name = choice.delta.function_call.name;
                            }
                            if (choice.delta.function_call.arguments) {
                                aggregatedResponse.choices[0].message.function_call.arguments += choice.delta.function_call.arguments;
                            }
                        }
                    }
                    if (choice.finish_reason) {
                        aggregatedResponse.choices[0].finish_reason = choice.finish_reason;
                    }
                }

                if (chunk.usage) {
                    aggregatedResponse.usage = chunk.usage;
                }
            }
            resolve(aggregatedResponse);
        } catch (error) {
            reject(error);
        }
    });
}

export function makeOpenAIOp(originalCreate: any) {
    return op(
        async function (...args: Parameters<typeof originalCreate>) {
            const [originalParams]: any[] = args;
            const params = { ...originalParams }; // Create a shallow copy of the params

            if (params.stream) {
                // Always include usage for internal tracking
                params.stream_options = {
                    ...params.stream_options,
                    include_usage: true
                };

                const result = await originalCreate(params);

                // If the user didn't originally request usage, filter it out
                if (!originalParams.stream_options?.include_usage) {
                    return {
                        [Symbol.asyncIterator]: async function* () {
                            for await (const chunk of result) {
                                if ('choices' in chunk && chunk.choices.length > 0) {
                                    // Only yield chunks with non-empty choices
                                    const filteredChunk = { ...chunk };
                                    delete filteredChunk.usage;  // Remove usage key if present
                                    yield filteredChunk;
                                }
                                // Usage-only chunks are filtered out
                            }
                        }
                    };
                }

                return result;
            } else {
                return await originalCreate(originalParams);
            }
        },
        {
            name: 'openai.chat.completions.create',
            summarize: (result) => ({
                usage: {
                    [result.model]: result.usage
                }
            }),
            aggregateStream: aggregateOpenAIStream
        }
    );
}

export function createPatchedOpenAI(apiKey: string): OpenAI {
    const openai = new OpenAI({ apiKey });

    const originalCreate = openai.chat.completions.create.bind(openai.chat.completions);
    // @ts-ignore
    openai.chat.completions.create = makeOpenAIOp(originalCreate);

    return openai;
}