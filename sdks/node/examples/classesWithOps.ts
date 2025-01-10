import OpenAI from 'openai';
import * as weave from 'weave';

class ExampleModel {
  private oaiClient: OpenAI;

  constructor() {
    this.oaiClient = weave.wrapOpenAI(new OpenAI());
    this.invoke = weave.op(this, this.invoke);
  }

  async invoke(input: string) {
    const response = await this.oaiClient.chat.completions.create({
      model: 'gpt-4o',
      messages: [{role: 'user', content: input}],
    });
    return response.choices[0].message.content;
  }
}

async function main() {
  await weave.init('examples');

  const model = new ExampleModel();
  await model.invoke('Tell me a joke');
}

main();
