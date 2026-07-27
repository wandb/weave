import OpenAI from 'openai';
import {wrapOpenAI} from '../../integrations/openai';

// Every other OpenAI test hand-builds its own client shape, so nothing checks
// the integration's method list against the SDK it actually ships against.
// That is how tracing for `chat.completions.parse` went quiet: openai-node v5
// moved the method out of `beta.chat` and the proxy kept looking in the old
// place. This test fails the next time upstream moves one of them.
describe('wrapOpenAI against the installed openai package', () => {
  test('wraps every method the integration traces', () => {
    const client = new OpenAI({apiKey: 'test-key'});
    const wrapped = wrapOpenAI(new OpenAI({apiKey: 'test-key'}));

    // The SDK keeps these methods on resource prototypes, so an unwrapped
    // client holds the identity a wrapped one has to differ from.
    expect(wrapped.chat.completions.create).not.toBe(
      client.chat.completions.create
    );
    expect(wrapped.chat.completions.parse).not.toBe(
      client.chat.completions.parse
    );
    expect(wrapped.images.generate).not.toBe(client.images.generate);
    expect(wrapped.responses.create).not.toBe(client.responses.create);
  });
});
