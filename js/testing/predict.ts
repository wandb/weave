import OpenAI from 'openai';
import {init, wrapOpenAI} from 'weave';

const main = async () => {
  const client = await init('weavejs');
  const oai = wrapOpenAI(new OpenAI());
  // oai.chat.completions.create({
  //   model: 'gpt-4o',
  //   messages: [{role: 'user', content: 'Hello, world!'}],
  // });
  console.log(oai.apiKey);
};

console.log('hello', init);
main();
