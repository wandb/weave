import {agentConversationPath} from '../index';
import {setGlobalDomain} from '../urls';

describe('agentConversationPath', () => {
  afterEach(() => {
    setGlobalDomain(null);
  });

  test('builds conversation URLs for default and configured domains', () => {
    // Default W&B domain before initialization.
    expect(agentConversationPath('team/project', 'conversation-1')).toBe(
      'https://wandb.ai/team/project/weave/agents/conversations/conversation-1'
    );

    // Configured domain and an app-provided conversation ID that needs escaping.
    setGlobalDomain('wandb.example.com');
    expect(
      agentConversationPath('team/project', 'customer/acme support?#')
    ).toBe(
      'https://wandb.example.com/team/project/weave/agents/conversations/customer%2Facme%20support%3F%23'
    );
  });
});
