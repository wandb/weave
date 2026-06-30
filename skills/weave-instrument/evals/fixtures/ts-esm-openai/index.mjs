import OpenAI from 'openai';

const MODEL = 'gpt-4o-mini';
const openai = new OpenAI();

const QUESTIONS = [
  'In one sentence, what is the capital of France?',
  'In one sentence, what causes ocean tides?',
];

async function answer(question) {
  const resp = await openai.chat.completions.create({
    model: MODEL,
    messages: [
      {role: 'system', content: 'Answer concisely.'},
      {role: 'user', content: question},
    ],
  });
  return resp.choices[0].message.content ?? '';
}

async function main() {
  for (const question of QUESTIONS) {
    console.log(`Q: ${question}`);
    console.log(`A: ${await answer(question)}\n`);
  }
}

main();
