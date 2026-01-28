import {WeaveClient} from './weaveClient';
import {ObjectRef, WeaveObject, WeaveObjectParameters} from './weaveObject';

export class Prompt extends WeaveObject {
  constructor(parameters: WeaveObjectParameters) {
    super(parameters);
  }
}

interface StringPromptParameters extends WeaveObjectParameters {
  content: string;
}

export class StringPrompt extends Prompt {
  content: string;

  constructor(parameters: StringPromptParameters) {
    super(parameters);
    this.content = parameters.content;
  }

  format(values: Record<string, any> = {}): string {
    return formatString(this.content, values);
  }

  static async get(client: WeaveClient, uri: string): Promise<StringPrompt> {
    const ref = ObjectRef.fromUri(uri);
    const data = await client.get(ref);
    return data as StringPrompt;
  }
}

interface MessagesPromptParameters extends WeaveObjectParameters {
  messages: Record<string, any>[];
}

export class MessagesPrompt extends Prompt {
  messages: Record<string, any>[];

  constructor(parameters: MessagesPromptParameters) {
    super(parameters);
    this.messages = parameters.messages;
  }

  private formatMessage(
    message: Record<string, any>,
    values: Record<string, any> = {}
  ): Record<string, any> {
    const formattedMessage = Object.fromEntries(
      Object.entries(message).map(([key, value]) => {
        if (typeof value === 'string') {
          return [key, formatString(value, values)];
        } else if (
          Array.isArray(value) &&
          value.every(item => typeof item === 'object' && item !== null)
        ) {
          return [key, value.map(item => this.formatMessage(item, values))];
        } else {
          return [key, value];
        }
      })
    );

    return formattedMessage;
  }

  format(values: Record<string, any> = {}): Record<string, any>[] {
    return this.messages.map(message => {
      return this.formatMessage(message, values);
    });
  }

  static async get(client: WeaveClient, uri: string): Promise<MessagesPrompt> {
    const ref = ObjectRef.fromUri(uri);
    const data = await client.get(ref);
    return data as MessagesPrompt;
  }
}

function formatString(str: string, kwargs: Record<string, any> = {}): string {
  return str.replace(/\{(\w+)(:[^}]+)?\}/g, (match, key) => {
    return kwargs[key] !== undefined ? kwargs[key] : match;
  });
}
