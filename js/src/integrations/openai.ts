import OpenAI from 'openai';
import { op } from '../clientApi';

export function makeOpenAIOp(originalCreate: any) {
    return op(
        async function (...args: Parameters<typeof originalCreate>) {
            return await originalCreate(...args);
        },
        {
            name: 'openai.chat.completions.create',
            summarize: (result) => ({
                usage: {
                    [result.model]: result.usage
                }
            })
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