import React, {
  createContext,
  Dispatch,
  useCallback,
  useContext,
  useReducer,
} from 'react';

import {Messages} from '../pages/ChatView/types';

// Action type constants
export const CREATE_PROMPT_ACTIONS = {
  SET_IS_OPEN: 'SET_IS_OPEN',
  SET_PROMPT_NAME: 'SET_PROMPT_NAME',
  SET_PROMPT_DESCRIPTION: 'SET_PROMPT_DESCRIPTION',
  SET_MESSAGES: 'SET_MESSAGES',
  SET_IS_LOADING: 'SET_IS_LOADING',
  SET_ERROR: 'SET_ERROR',
  SET_DRAWER_WIDTH: 'SET_DRAWER_WIDTH',
  SET_IS_FULLSCREEN: 'SET_IS_FULLSCREEN',
  RESET: 'RESET',
} as const;

// State interface
export interface CreatePromptState {
  isOpen: boolean;
  promptName: string;
  messages: Messages;
  isLoading: boolean;
  error: string | null;
  drawerWidth: number;
  isFullscreen: boolean;
}

// Action types
export type CreatePromptAction =
  | {type: typeof CREATE_PROMPT_ACTIONS.SET_IS_OPEN; payload: boolean}
  | {type: typeof CREATE_PROMPT_ACTIONS.SET_PROMPT_NAME; payload: string}
  | {
      type: typeof CREATE_PROMPT_ACTIONS.SET_MESSAGES;
      payload: Messages;
    }
  | {type: typeof CREATE_PROMPT_ACTIONS.SET_IS_LOADING; payload: boolean}
  | {type: typeof CREATE_PROMPT_ACTIONS.SET_ERROR; payload: string | null}
  | {type: typeof CREATE_PROMPT_ACTIONS.SET_DRAWER_WIDTH; payload: number}
  | {type: typeof CREATE_PROMPT_ACTIONS.SET_IS_FULLSCREEN; payload: boolean}
  | {type: typeof CREATE_PROMPT_ACTIONS.RESET};

// Initial state
const initialState: CreatePromptState = {
  isOpen: false,
  promptName: '',
  messages: [],
  isLoading: false,
  error: null,
  drawerWidth: 800,
  isFullscreen: false,
};

// Reducer function
function createPromptReducer(
  state: CreatePromptState,
  action: CreatePromptAction
): CreatePromptState {
  switch (action.type) {
    case CREATE_PROMPT_ACTIONS.SET_IS_OPEN:
      return {...state, isOpen: action.payload};
    case CREATE_PROMPT_ACTIONS.SET_PROMPT_NAME:
      return {...state, promptName: action.payload};
    case CREATE_PROMPT_ACTIONS.SET_MESSAGES:
      return {...state, messages: action.payload};
    case CREATE_PROMPT_ACTIONS.SET_IS_LOADING:
      return {...state, isLoading: action.payload};
    case CREATE_PROMPT_ACTIONS.SET_ERROR:
      return {...state, error: action.payload};
    case CREATE_PROMPT_ACTIONS.SET_DRAWER_WIDTH:
      return {...state, drawerWidth: action.payload};
    case CREATE_PROMPT_ACTIONS.SET_IS_FULLSCREEN:
      return {...state, isFullscreen: action.payload};
    case CREATE_PROMPT_ACTIONS.RESET:
      return initialState;
    default:
      return state;
  }
}

// Context interface
interface CreatePromptContextType {
  state: CreatePromptState;
  dispatch: Dispatch<CreatePromptAction>;
  handleCloseDrawer: () => void;
  handlePublishPrompt: () => void;
  clearPrompt: () => void;
}

// Create the context
const CreatePromptContext = createContext<CreatePromptContextType | undefined>(
  undefined
);

// Provider component
export const CreatePromptProvider: React.FC<{
  children: React.ReactNode;
  onPublishPrompt: (name: string, rows: any[]) => void;
}> = ({children, onPublishPrompt}) => {
  return (
    <CreatePromptProviderInner onPublishPrompt={onPublishPrompt}>
      {children}
    </CreatePromptProviderInner>
  );
};

// Inner provider that has access to the editor context
const CreatePromptProviderInner: React.FC<{
  children: React.ReactNode;
  onPublishPrompt: (name: string, rows: any[]) => void;
}> = ({children, onPublishPrompt}) => {
  const [state, dispatch] = useReducer(createPromptReducer, initialState);

  // Handle drawer close
  const handleCloseDrawer = useCallback(() => {
    dispatch({type: CREATE_PROMPT_ACTIONS.SET_IS_OPEN, payload: false});
    dispatch({type: CREATE_PROMPT_ACTIONS.SET_MESSAGES, payload: []});
  }, []);

  // Handle publish prompt
  const handlePublishPrompt = useCallback(() => {
    if (state.messages) {
      // Call the onPublishPrompt callback with just the name and messages
      onPublishPrompt(state.promptName, state.messages);

      // Reset the state
      dispatch({type: CREATE_PROMPT_ACTIONS.RESET});
    }
  }, [state.messages, state.promptName, onPublishPrompt]);

  // Handle clear prompt
  const clearPrompt = useCallback(() => {
    dispatch({type: CREATE_PROMPT_ACTIONS.SET_MESSAGES, payload: []});
  }, []);

  return (
    <CreatePromptContext.Provider
      value={{
        state,
        dispatch,
        handleCloseDrawer,
        handlePublishPrompt,
        clearPrompt,
      }}>
      {children}
    </CreatePromptContext.Provider>
  );
};

// Hook for using the context
export const useCreatePromptContext = () => {
  const context = useContext(CreatePromptContext);
  if (context === undefined) {
    throw new Error(
      'useCreatePromptContext must be used within a CreatePromptProvider'
    );
  }
  return context;
};
