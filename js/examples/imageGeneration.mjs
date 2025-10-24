import { init, wrapOpenAI } from 'weave';

async function main() {
    const client = await init('weavejs-img');
    const openai = wrapOpenAI();

    // Generate an image
    const result = await openai.images.generate({
        prompt: "A cute baby sea otter",
        n: 3,
        size: "256x256",
        response_format: "b64_json"
    });

    console.log("Generated image result:", result);
}

main();

