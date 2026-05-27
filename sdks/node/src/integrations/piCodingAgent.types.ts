export type {AgentMessage as PiAgentMessage} from '@earendil-works/pi-agent-core';

export type {
  AssistantMessage as PiAssistantMessage,
  Model as PiModel,
} from '@earendil-works/pi-ai';

export type {
  ExtensionEvent as PiExtensionEvent,
  ExtensionAPI as PiExtensionApi,
  ExtensionContext as PiExtensionContext,
} from '@earendil-works/pi-coding-agent';

import type {ExtensionAPI} from '@earendil-works/pi-coding-agent';

/** Shape returned by createOtelExtension — passed to createAgentSession({ extensions: [...] }) */
export interface PiExtensionDefinition {
  name: string;
  setup(pi: ExtensionAPI): Promise<void> | void;
}
