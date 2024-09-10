// TODO: lock this down
export type Data = Record<string, any>;

export type Placeholder = {
  name: string;
  type: string;
  default?: string;
};

export type ImageUrl = {
  url: string;
};

export type InternalMessage = {
  type: 'text' | 'image_url';
  text?: string;
  image_url?: ImageUrl;
};

export type MessagePart = string | Placeholder | InternalMessage;

// TODO: Can we tighten this up?
export type ToolCall = Record<string, any>;

export type Message = {
  role: string;
  content?: string | MessagePart[];
  tool_calls?: ToolCall[];
};

export type Messages = Message[];
