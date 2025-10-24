import { init, op, wrapOpenAI } from 'weave';

const openai = wrapOpenAI();

async function extractDinos(input) {
    const response = await openai.chat.completions.create({
        model: 'gpt-4o',
        messages: [{ role: 'user', content: `In JSON format extract a list of 'dinosaurs', with their 'name', their 'common_name', and whether its 'diet' is a herbivore or carnivore: ${input}` }],
    });
    return response.choices[0].message.content;
}
const extractDinosOp = op(extractDinos);

async function main() {
    await init('weave-quickstart');
    const result = await extractDinosOp("I watched as a Tyrannosaurus rex (T. rex) chased after a Triceratops (Trike), both carnivore and herbivore locked in an ancient dance. Meanwhile, a gentle giant Brachiosaurus (Brachi) calmly munched on treetops, blissfully unaware of the chaos below.");
    console.log(result);
}

main();

