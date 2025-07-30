import React, {useCallback, useState} from 'react';
import {Button} from '../../../../Button';
import {Tailwind} from '../../../../Tailwind';
import {TextField} from '../../../../Form/TextField';
import {WaveLoader} from '../../../../Loaders/WaveLoader';
import {Messages} from '../pages/ChatView/types';
import {ResizableDrawer} from '../pages/common/TailwindResizableDrawer';
import {TabPrompt} from '../pages/ObjectsPage/Tabs/TabPrompt';
import {
  CREATE_PROMPT_ACTIONS,
  CreatePromptProvider,
  useCreatePromptContext,
} from './CreatePromptDrawerContext';
import {validatePromptName} from './promptNameValidation';

interface CreatePromptDrawerProps {
  open: boolean;
  onClose: () => void;
  onSavePrompt: (name: string, rows: any[]) => void;
  isCreating?: boolean;
}

export const CreatePromptDrawer: React.FC<CreatePromptDrawerProps> = ({
  open,
  onClose,
  onSavePrompt,
  isCreating = false,
}) => {
  return (
    <CreatePromptProvider onPublishPrompt={onSavePrompt}>
      <CreatePromptDrawerContent
        open={open}
        onClose={onClose}
        isCreating={isCreating}
      />
    </CreatePromptProvider>
  );
};

const CreatePromptDrawerContent: React.FC<{
  open: boolean;
  onClose: () => void;
  isCreating?: boolean;
}> = ({open, onClose, isCreating = false}) => {
  const {state, dispatch, handleCloseDrawer, handlePublishPrompt} =
    useCreatePromptContext();

  const {promptName, messages, isLoading, error, drawerWidth, isFullscreen} =
    state;

  const setMessages = useCallback(
    (messages: Messages) => {
      dispatch({
        type: CREATE_PROMPT_ACTIONS.SET_MESSAGES,
        payload: messages,
      });
    },
    [dispatch]
  );

  const [nameError, setNameError] = useState<string | null>(null);

  const handleNameChange = useCallback(
    (value: string) => {
      dispatch({
        type: CREATE_PROMPT_ACTIONS.SET_PROMPT_NAME,
        payload: value,
      });

      const validationResult = validatePromptName(value);
      setNameError(validationResult.error);
    },
    [dispatch]
  );

  const wrappedOnClose = useCallback(() => {
    handleCloseDrawer();
    onClose();
  }, [handleCloseDrawer, onClose]);

  const handleToggleFullscreen = useCallback(() => {
    dispatch({
      type: CREATE_PROMPT_ACTIONS.SET_IS_FULLSCREEN,
      payload: !isFullscreen,
    });
  }, [dispatch, isFullscreen]);

  return (
    <Tailwind>
      <ResizableDrawer
        data-testid="create-prompt-drawer"
        open={open}
        onClose={wrappedOnClose}
        defaultWidth={isFullscreen ? window.innerWidth - 73 : drawerWidth}
        setWidth={width =>
          !isFullscreen &&
          dispatch({
            type: CREATE_PROMPT_ACTIONS.SET_DRAWER_WIDTH,
            payload: width,
          })
        }
        headerContent={
          <div className="tw-style flex justify-between items-center h-[44px] min-h-[44px] pl-16 pr-8 border-b border-moon-250 dark:border-moon-800 flex-shrink-0">
            <h2 className="text-[20px] font-semibold font-['Source_Sans_Pro'] text-moon-950 dark:text-moon-50">
              Create new prompt
            </h2>
            <div className="flex gap-8">
              <Button
                onClick={handleToggleFullscreen}
                variant="ghost"
                icon={isFullscreen ? 'minimize-mode' : 'full-screen-mode-expand'}
                tooltip={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
              />
              <Button
                onClick={wrappedOnClose}
                variant="ghost"
                icon="close"
                tooltip="Close"
              />
            </div>
          </div>
        }>
        <div className="tw-style flex flex-col flex-1 overflow-hidden">
          {isCreating || isLoading ? (
            <div className="flex justify-center items-center flex-1">
              <WaveLoader size="huge" />
            </div>
          ) : (
            <>
              <div className="p-16 overflow-auto flex flex-col min-h-0">
                {error && (
                  <div className="mb-16 p-16 bg-red-300 dark:bg-red-700 rounded text-red-700 dark:text-red-300">
                    <p className="font-['Source_Sans_Pro']">{error}</p>
                  </div>
                )}

                <div className="mb-16">
                  <label className="block font-['Source_Sans_Pro'] font-semibold mb-8 text-moon-950 dark:text-moon-50 text-left">
                    Prompt name
                  </label>
                  <TextField
                    value={promptName}
                    onChange={handleNameChange}
                    placeholder="Enter a name for your prompt"
                    errorState={nameError !== null}
                  />
                  {nameError && (
                    <p className="font-['Source_Sans_Pro'] text-red-500 dark:text-red-400 text-14 mt-8">
                      {nameError}
                    </p>
                  )}
                  <p className="font-['Source_Sans_Pro'] text-moon-500 dark:text-moon-400 font-normal text-[14px] mt-8 text-left">
                    Valid prompt names must start with a letter or number and can
                    only contain letters, numbers, hyphens, and underscores.
                  </p>
                </div>
              </div>

              <div className="flex-1 px-16 min-h-0 overflow-hidden font-['Source_Sans_Pro'] text-moon-950 dark:text-moon-50 text-left">
                <TabPrompt
                  messages={messages}
                  setMessages={setMessages}
                  isEditing={true}
                />
              </div>
              <div className="py-16 px-16 border-t border-moon-250 dark:border-moon-800 bg-white dark:bg-moon-950 w-full flex flex-shrink-0 block">
                <Button
                  data-testid="create-prompt-submit-button"
                  onClick={handlePublishPrompt}
                  variant="primary"
                  disabled={
                    !promptName || nameError !== null || messages.length === 0
                  }
                  tooltip="Save and publish the prompt"
                  style={{
                    width: '100%',
                  }}
                  twWrapperStyles={{
                    width: '100%',
                    display: 'block',
                  }}>
                  Publish Prompt
                </Button>
              </div>
            </>
          )}
        </div>
      </ResizableDrawer>
    </Tailwind>
  );
};
