import {instrumentAnthropic} from '../../integrations/anthropic';
import {
  instrumentClaudeAgentSdk,
  wrapClaudeAgentSdk,
} from '../../integrations/claudeAgentSdk';
import {
  commonPatchGoogleADK,
  instrumentGoogleADK,
  WeaveAdkPlugin,
} from '../../integrations/googleAdk';
import {
  commonPatchGoogleGenAI,
  instrumentGoogleGenAI,
  wrapGoogleGenAI,
} from '../../integrations/googleGenAI';
import instrumentations, {
  getLoadOrderDependencyOwners,
  isLoadOrderWarningSuppressed,
} from '../../integrations/instrumentations';
import {instrumentOpenAI, wrapOpenAI} from '../../integrations/openai';
import {
  createOpenAIAgentsTracingProcessor,
  instrumentOpenAIAgent,
  instrumentOpenAIAgents,
} from '../../integrations/openai.agent';
import {
  instrumentOpenAIRealtimeAgent,
  patchRealtimeSession,
} from '../../integrations/openai.realtime.agent';

const MODULES = [
  'openai',
  '@anthropic-ai/sdk',
  '@anthropic-ai/claude-agent-sdk',
  '@google/adk',
  '@google/genai',
  '@openai/agents',
  '@openai/agents-realtime',
];

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

class FakeBatches {
  create() {}
  retrieve() {}
  results() {}
}

class FakeMessages {
  static Batches = FakeBatches;
  create() {}
  stream() {}
}

class FakeRunner {
  async *runAsync() {}
}

class FakeRealtimeSession {
  sendAudio() {}
}

function cjsHook(key: string) {
  return instrumentations.get(key)[0].hook;
}

// Both registries are process-wide singletons; each case clears them first.
function registry<T>(key: string): T {
  return (globalThis as any)[Symbol.for(key)];
}

// What a case leaves behind: modules suppressed outright, and modules
// suppressed only while their listed owners are the ones that loaded them.
function suppression() {
  const owners: Record<string, string[]> = {};
  for (const moduleName of MODULES) {
    const moduleOwners = [...getLoadOrderDependencyOwners(moduleName)].sort();
    if (moduleOwners.length > 0) {
      owners[moduleName] = moduleOwners;
    }
  }
  return {suppressed: MODULES.filter(isLoadOrderWarningSuppressed), owners};
}

const NONE = {suppressed: [], owners: {}};

beforeAll(() => {
  instrumentOpenAI();
  instrumentAnthropic();
  instrumentClaudeAgentSdk();
  instrumentGoogleADK();
  instrumentGoogleGenAI();
  instrumentOpenAIAgent();
  instrumentOpenAIRealtimeAgent();
});

beforeEach(() => {
  registry<Set<string>>('_weave_load_order_warning_suppressed').clear();
  registry<Map<string, Set<string>>>(
    '_weave_load_order_dependency_owners'
  ).clear();
});

describe('load-order warning suppression', () => {
  test.each<[string, () => unknown, ReturnType<typeof suppression>]>([
    // Export swaps: a reference taken before the hook stays unpatched.
    [
      'openai require hook',
      () => new (cjsHook('openai@index.js')({OpenAI: FakeOpenAI}).OpenAI)(),
      NONE,
    ],
    [
      'genai require hook',
      () =>
        new (commonPatchGoogleGenAI({
          GoogleGenAI: FakeGoogleGenAI,
        }).GoogleGenAI)({}),
      NONE,
    ],
    [
      'claude require hook',
      () =>
        cjsHook('@anthropic-ai/claude-agent-sdk@sdk.mjs')({
          query: () => undefined,
        }),
      NONE,
    ],
    [
      'realtime require hook',
      () =>
        cjsHook('@openai/agents-realtime@dist/index.js')({
          RealtimeSession: FakeRealtimeSession,
        }),
      NONE,
    ],
    ['patchRealtimeSession()', () => patchRealtimeSession(), NONE],
    // Explicit registration.
    [
      'wrapOpenAI()',
      () => wrapOpenAI(new FakeOpenAI() as any),
      {suppressed: ['openai'], owners: {}},
    ],
    [
      'wrapGoogleGenAI()',
      () => wrapGoogleGenAI(new FakeGoogleGenAI() as any),
      {suppressed: ['@google/genai'], owners: {}},
    ],
    [
      'wrapClaudeAgentSdk()',
      () => wrapClaudeAgentSdk({query: () => undefined}),
      {suppressed: ['@anthropic-ai/claude-agent-sdk'], owners: {}},
    ],
    [
      'new WeaveAdkPlugin()',
      () => new WeaveAdkPlugin(),
      {suppressed: ['@google/adk'], owners: {}},
    ],
    [
      'createOpenAIAgentsTracingProcessor()',
      () => createOpenAIAgentsTracingProcessor(),
      {
        suppressed: ['@openai/agents'],
        owners: {'@openai/agents-realtime': ['@openai/agents']},
      },
    ],
    [
      'instrumentOpenAIAgents()',
      () => instrumentOpenAIAgents(),
      {
        suppressed: ['@openai/agents'],
        owners: {'@openai/agents-realtime': ['@openai/agents']},
      },
    ],
    // Prototype patches: the loader suppresses the one file it patched, by the
    // registration flag checked below, so the hooks themselves record nothing.
    [
      'ADK require hook',
      () => commonPatchGoogleADK({Runner: FakeRunner} as any),
      NONE,
    ],
    [
      'Anthropic require hook',
      () =>
        cjsHook('@anthropic-ai/sdk@index.js')({
          Anthropic: {Messages: FakeMessages},
        }),
      NONE,
    ],
    // Hooked modules that another integration loads for its own use.
    [
      'instrumentGoogleADK()',
      () => instrumentGoogleADK(),
      {suppressed: [], owners: {'@google/genai': ['@google/adk']}},
    ],
    [
      'instrumentOpenAIAgent()',
      () => instrumentOpenAIAgent(),
      {suppressed: [], owners: {openai: ['@openai/agents-openai']}},
    ],
  ])('%s', async (_name, run, expected) => {
    await run();
    expect(suppression()).toEqual(expected);
  });
});

test('only the hooks whose patch reaches earlier references are flagged', () => {
  const flagged = [...instrumentations]
    .filter(([, candidates]: [string, any[]]) =>
      candidates.some(candidate => candidate.reachesEarlierReferences)
    )
    .map(([key]: [string, any[]]) => key)
    .sort();
  expect(flagged).toEqual([
    '@anthropic-ai/sdk@index.js',
    '@google/adk@dist/cjs/index.js',
  ]);
});
