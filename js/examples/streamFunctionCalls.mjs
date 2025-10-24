import { init, op, wrapOpenAI } from 'weave';
import OpenAI from 'openai';

const openai = wrapOpenAI();
// const openai = new OpenAI();

async function extractDinos(input) {
    const functions = [
        {
            name: 'get_current_weather',
            description: 'Get the current weather for a given location.',
            parameters: {
                type: 'object',
                properties: {
                    location: {
                        type: 'string',
                        description: 'The name of the city or location to get weather for.',
                    },
                },
                required: ['location'],
            },
        },
        {
            name: 'get_time_in_location',
            description: 'Get the current time for a given location.',
            parameters: {
                type: 'object',
                properties: {
                    location: {
                        type: 'string',
                        description: 'The name of the city or location to get the current time for.',
                    },
                },
                required: ['location'],
            },
        },
    ];
    const response = await openai.chat.completions.create({
        stream: true,
        // stream_options: { "include_usage": true },
        model: 'gpt-4o',
        functions: functions,
        messages: [{ role: 'user', content: `what is the weather and time in ${input}? Tell me what your'e going to do as you do it.` }],
    });
    console.log(JSON.stringify(response));
    for await (const chunk of response) {
        console.log(JSON.stringify(chunk));
    }
    // return response.choices[0].message.content;
}
const extractDinosOp = op(extractDinos);

async function main() {
    await init('weave-quickstart');
    const result = await extractDinosOp("London");
    console.log(result);
}

main();

