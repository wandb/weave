import {runAgent} from './agent';

const QUESTIONS = [
  "What's the weather in Tokyo?",
  "What's the weather in Paris?",
];

async function main(): Promise<void> {
  for (const question of QUESTIONS) {
    console.log(`USER:  ${question}`);
    const answer = await runAgent(question);
    console.log(`AGENT: ${answer}\n`);
  }
}

main();
