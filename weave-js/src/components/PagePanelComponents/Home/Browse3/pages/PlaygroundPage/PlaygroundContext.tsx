import {createContext, useContext} from 'react';

export type PlaygroundContextType = {
  isPlayground?: boolean;
  deleteMessage?: (messageIndex: number, responseIndexes?: number[]) => void;
  editMessage?: (messageIndex: number, newMessage: any) => void;
  deleteChoice?: (choiceIndex: number) => void;
  editChoice?: (choiceIndex: number, newChoice: any) => void;
  addMessage?: (newMessage: any) => void;
  retry?: (messageIndex: number, isChoice?: boolean) => void;
  sendMessage?: (
    role: 'assistant' | 'user' | 'tool',
    content: string,
    toolCallId?: string
  ) => void;
};

// Create a new context for the isPlayground value, and the playground chat functions
// isPlayground is the only required value
export const PlaygroundContext = createContext<PlaygroundContextType>({
  isPlayground: false,
});

// Create a custom hook to use the PlaygroundContext
export const usePlaygroundContext = () => useContext(PlaygroundContext);
