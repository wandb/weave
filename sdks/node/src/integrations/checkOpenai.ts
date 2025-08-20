// Manual test for checking openai client

import {OpenAI} from 'openai';
import {wrapOpenAI, init} from '..';
import {z} from 'zod';
import {zodResponseFormat} from 'openai/helpers/zod';

async function betaParseCall(client: OpenAI) {
  return await client.beta.chat.completions.parse({
    model: 'gpt-4o-2024-08-06',
    temperature: 0.7,
    messages: [
      {
        role: 'user',
        content: 'What is the capital of the US?',
      },
    ],
    response_format: zodResponseFormat(z.object({name: z.string()}), 'result'),
  });
}

async function standardCall(client: OpenAI) {
  return await client.chat.completions.create({
    model: 'gpt-4o-2024-08-06',
    temperature: 0.7,
    messages: [
      {
        role: 'user',
        content: 'What is the capital of the US?',
      },
    ],
    response_format: zodResponseFormat(z.object({name: z.string()}), 'result'),
  });
}

async function streamCall(client: OpenAI) {
  return await client.chat.completions.create({
    model: 'gpt-4o-2024-08-06',
    temperature: 0.7,
    messages: [
      {
        role: 'user',
        content: 'What is the capital of the US?',
      },
    ],
    stream: true,
    response_format: zodResponseFormat(z.object({name: z.string()}), 'result'),
  });
}

async function callTests(openai: OpenAI) {
  try {
    console.log('  BETA PARSE CALL');
    const response = await betaParseCall(openai);
    console.log('    SUCCESS', JSON.stringify(response).length);
  } catch (e) {
    console.log('    ERROR', e);
  }
  try {
    console.log('  STANDARD CALL');
    const response = await standardCall(openai);
    console.log('    SUCCESS', JSON.stringify(response).length);
  } catch (e) {
    console.log('    ERROR', e);
  }
  try {
    console.log('  STREAM CALL');
    const response = await streamCall(openai);
    let fullRes = '';
    for await (const chunk of response) {
      fullRes += JSON.stringify(chunk);
    }
    // console.log("FULL RESPONSE", fullRes);
    console.log('    SUCCESS', fullRes.length);
  } catch (e) {
    console.log('    ERROR', e);
  }
}

export async function oaiParse<T extends z.ZodTypeAny>() {
  const openai = new OpenAI({timeout: 120 * 1000});
  console.log('OPENAI CLIENT TESTS');
  await callTests(openai);

  const client = wrapOpenAI(openai);
  console.log('WRAPPED CLIENT TESTS');
  await callTests(client);

  await init('weavejs-dev-asynctest');
  console.log('WEAVE LOGGING TESTS');
  await callTests(client);
}

oaiParse().then(result => console.log(result));
