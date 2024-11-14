import {createContext, useContext} from 'react';

export type PlaygroundContextType = {
  isPlayground: boolean;
  deleteMessage: (messageIndex: number, responseIndexes?: number[]) => void;
  editMessage: (messageIndex: number, newMessage: any) => void;
  deleteChoice: (choiceIndex: number) => void;
  editChoice: (choiceIndex: number, newChoice: any) => void;
  addMessage: (newMessage: any) => void;
  retry: (messageIndex: number, isChoice?: boolean) => void;
  sendMessage: (
    role: 'assistant' | 'user' | 'tool',
    content: string,
    toolCallId?: string
  ) => void;
};

const DEFAULT_CONTEXT: PlaygroundContextType = {
  isPlayground: false,
  deleteMessage: () => {},
  editMessage: () => {},
  deleteChoice: () => {},
  editChoice: () => {},
  addMessage: () => {},
  retry: () => {},
  sendMessage: () => {},
};

// Create context that can be undefined
export const PlaygroundContext = createContext<
  PlaygroundContextType | undefined
>(DEFAULT_CONTEXT);

// Custom hook that handles the undefined context
export const usePlaygroundContext = () => {
  const context = useContext(PlaygroundContext);
  return context ?? DEFAULT_CONTEXT;
};
