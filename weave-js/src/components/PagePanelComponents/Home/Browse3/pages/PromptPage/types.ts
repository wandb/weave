type Placeholder = {
  name: string;
  type: string;
  default?: string;
};

type MessagePart = string | Placeholder;

type Message = {
  role: string;
  content: MessagePart[];
};

type Messages = Message[];
