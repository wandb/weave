import {createContext, useContext} from 'react';

import {Message} from '../ChatView/types';
import {PlaygroundMessageRole} from './types';

export type PlaygroundContextType = {
  isPlayground: boolean;
  addMessage: (newMessage: Message) => void;
  editMessage: (messageIndex: number, newMessage: Message) => void;
  deleteMessage: (messageIndex: number, responseIndexes?: number[]) => void;

  editChoice: (choiceIndex: number, newChoice: Message) => void;
  deleteChoice: (messageIndex: number, choiceIndex: number) => void;

  retry: (messageIndex: number, choiceIndex?: number) => void;
  sendMessage: (
    role: PlaygroundMessageRole,
    content: string,
    toolCallId?: string
  ) => void;

  setSelectedChoiceIndex: (choiceIndex: number) => void;
};

const DEFAULT_CONTEXT: PlaygroundContextType = {
  isPlayground: false,
  addMessage: () => {},
  editMessage: () => {},
  deleteMessage: () => {},

  editChoice: () => {},
  deleteChoice: () => {},

  retry: () => {},
  sendMessage: () => {},
  setSelectedChoiceIndex: () => {},
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
