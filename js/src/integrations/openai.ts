import OpenAI from 'openai';
import { op } from '../op';
import { weaveImage } from '../media';

const openAIStreamReducer = {
    initialState: {
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
    },
    reduceFn: (state: any, chunk: any) => {
        if (chunk.id) state.id = chunk.id;
        if (chunk.object) state.object = chunk.object;
        if (chunk.created) state.created = chunk.created;
        if (chunk.model) state.model = chunk.model;

        if (chunk.choices && chunk.choices.length > 0) {
            const choice = chunk.choices[0];
            if (choice.delta) {
                if (choice.delta.role) {
                    state.choices[0].message.role = choice.delta.role;
                }
                if (choice.delta.content) {
                    state.choices[0].message.content += choice.delta.content;
                }
                if (choice.delta.function_call) {
                    if (!state.choices[0].message.function_call) {
                        state.choices[0].message.function_call = { name: '', arguments: '' };
                    }
                    if (choice.delta.function_call.name) {
                        state.choices[0].message.function_call.name = choice.delta.function_call.name;
                    }
                    if (choice.delta.function_call.arguments) {
                        state.choices[0].message.function_call.arguments += choice.delta.function_call.arguments;
                    }
                }
            }
            if (choice.finish_reason) {
                state.choices[0].finish_reason = choice.finish_reason;
            }
        }

        if (chunk.usage) {
            state.usage = chunk.usage;
        }

        return state;
    }
};

export function makeOpenAIChatCompletionsOp(originalCreate: any) {
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

                return await originalCreate(params);
            } else {
                return await originalCreate(originalParams);
            }
        },
        {
            name: 'openai.chat.completions.create',
            parameterNames: 'useParam0Object',
            summarize: (result) => ({
                usage: {
                    [result.model]: result.usage
                }
            }),
            streamReducer: openAIStreamReducer
        }
    );
}

export function makeOpenAIImagesGenerateOp(originalGenerate: any) {
    return op(
        async function (...args: Parameters<typeof originalGenerate>) {
            const result = await originalGenerate(...args);

            // Process the result to convert image data to WeaveImage
            if (result.data) {
                result.data = await Promise.all(result.data.map(async (item: any) => {
                    if (item.b64_json) {
                        const buffer = Buffer.from(item.b64_json, 'base64');
                        return weaveImage({ data: buffer, imageType: 'png' });
                    }
                    return item;
                }));
            }

            return result;
        },
        {
            name: 'openai.images.generate',
            summarize: (result) => ({
                usage: {
                    'dall-e': {
                        images_generated: result.data.length
                    }
                }
            })
        }
    );
}

export function wrapOpenAI(openai?: OpenAI): OpenAI {
    if (!openai) {
        openai = new OpenAI();
    }

    const originalCreate = openai.chat.completions.create.bind(openai.chat.completions);
    // @ts-ignore
    openai.chat.completions.create = makeOpenAIChatCompletionsOp(originalCreate);

    const originalGenerate = openai.images.generate.bind(openai.images);
    // @ts-ignore
    openai.images.generate = makeOpenAIImagesGenerateOp(originalGenerate);

    return openai;
}