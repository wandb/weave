import {createContext, useContext} from 'react';

// Create a new context for the isPlayground value
export const PlaygroundContext = createContext<{
  isPlayground: boolean;
  deleteMessage?: (messageIndex: number) => void;
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
}>({isPlayground: false});

// Create a custom hook to use the PlaygroundContext
export const usePlaygroundContext = () => useContext(PlaygroundContext);
