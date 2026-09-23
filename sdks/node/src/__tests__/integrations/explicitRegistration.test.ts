import instrumentations, {
  isRegisteredExplicitly,
} from '../../integrations/instrumentations';
import {wrapClaudeAgentSdk} from '../../integrations/claudeAgentSdk';
import {WeaveAdkPlugin} from '../../integrations/googleAdk';
import {
  commonPatchGoogleGenAI,
  wrapGoogleGenAI,
} from '../../integrations/googleGenAI';
import {instrumentOpenAI, wrapOpenAI} from '../../integrations/openai';

class FakeOpenAI {
  chat = {completions: {create: () => undefined}};
  images = {generate: () => undefined};
}

class FakeGoogleGenAI {
  models = {
    generateContent: () => undefined,
    generateContentStream: () => undefined,
  };
}

const EXPLICIT_MODULES = [
  'openai',
  '@google/genai',
  '@anthropic-ai/claude-agent-sdk',
  '@google/adk',
];

describe('explicit registration', () => {
  test('only the explicit APIs count, not the require hook', () => {
    instrumentOpenAI();
    const [{hook}] = instrumentations.get('openai@index.js');
    const hookedOpenAI = hook({OpenAI: FakeOpenAI}, 'openai', '');
    new hookedOpenAI.OpenAI();
    const hookedGenAI = commonPatchGoogleGenAI({GoogleGenAI: FakeGoogleGenAI});
    new hookedGenAI.GoogleGenAI({});
    expect(EXPLICIT_MODULES.filter(isRegisteredExplicitly)).toEqual([]);

    wrapOpenAI(new FakeOpenAI() as any);
    wrapGoogleGenAI(new FakeGoogleGenAI() as any);
    wrapClaudeAgentSdk({query: () => undefined});
    new WeaveAdkPlugin();
    expect(EXPLICIT_MODULES.filter(isRegisteredExplicitly)).toEqual(
      EXPLICIT_MODULES
    );
  });
});
