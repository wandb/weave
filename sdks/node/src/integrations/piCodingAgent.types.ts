export type {AgentMessage as PiAgentMessage} from "@mariozechner/pi-agent-core";

export type {AssistantMessage as PiAssistantMessage, Model as PiModel} from "@mariozechner/pi-ai";

export type {ExtensionEvent as PiExtensionEvent, ExtensionAPI as PiExtensionApi, ExtensionContext as PiExtensionContext} from "@mariozechner/pi-coding-agent"

import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";

/** Shape returned by createOtelExtension — passed to createAgentSession({ extensions: [...] }) */
export interface PiExtensionDefinition {
  name: string;
  setup(pi: ExtensionAPI): Promise<void> | void;
}
