import {Box, Typography} from '@mui/material';
import React, {useCallback, useState} from 'react';

import {Button} from '../../../../Button';
import {TextField} from '../../../../Form/TextField';
import {WaveLoader} from '../../../../Loaders/WaveLoader';
import {Messages} from '../pages/ChatView/types';
import {ResizableDrawer} from '../pages/common/ResizableDrawer';
import {TabPrompt} from '../pages/ObjectsPage/Tabs/TabPrompt';
import {
  CREATE_PROMPT_ACTIONS,
  CreatePromptProvider,
  useCreatePromptContext,
} from './CreatePromptDrawerContext';
import {validatePromptName} from './promptNameValidation';

// Define typography style with Source Sans Pro font
const typographyStyle = {fontFamily: 'Source Sans Pro'};

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
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            height: 44,
            minHeight: 44,
            pl: 2,
            pr: 1,
            borderBottom: '1px solid',
            borderColor: 'divider',
          }}>
          <Typography variant="h6" sx={{...typographyStyle, fontWeight: 600}}>
            Create new prompt
          </Typography>
          <Box sx={{display: 'flex', gap: 1}}>
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
          </Box>
        </Box>
      }>
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          overflow: 'hidden',
        }}>
        {isCreating || isLoading ? (
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              flex: 1,
            }}>
            <WaveLoader size="huge" />
          </Box>
        ) : (
          <>
            <Box
              sx={{
                p: 2,
                overflow: 'auto',
                display: 'flex',
                flexDirection: 'column',
                minHeight: 0,
              }}>
              {error && (
                <Box
                  sx={{
                    mb: 2,
                    p: 2,
                    bgcolor: 'error.light',
                    borderRadius: 1,
                    color: 'error.dark',
                  }}>
                  <Typography sx={typographyStyle}>{error}</Typography>
                </Box>
              )}

              <Box sx={{mb: 2}}>
                <Typography
                  sx={{
                    ...typographyStyle,
                    fontWeight: 600,
                    mb: '8px',
                  }}>
                  Prompt name
                </Typography>
                <TextField
                  value={promptName}
                  onChange={handleNameChange}
                  placeholder="Enter a name for your prompt"
                  errorState={nameError !== null}
                />
                {nameError && (
                  <Typography
                    sx={{
                      ...typographyStyle,
                      color: 'error.main',
                      fontSize: '0.875rem',
                      mt: 1,
                    }}>
                    {nameError}
                  </Typography>
                )}
                <Typography
                  sx={{
                    ...typographyStyle,
                    color: 'text.secondary',
                    fontWeight: 400,
                    fontSize: '0.875rem',
                    mt: 1,
                  }}>
                  Valid prompt names must start with a letter or number and can
                  only contain letters, numbers, hyphens, and underscores.
                </Typography>
              </Box>
            </Box>

            <Box sx={{flexGrow: 1, px: 2}}>
              <TabPrompt
                messages={messages}
                setMessages={setMessages}
                isEditing={true}
              />
            </Box>

            {/* Publish button at the bottom */}
            <Box
              sx={{
                py: 2,
                px: 0,
                borderTop: '1px solid',
                borderColor: 'divider',
                backgroundColor: 'background.paper',
                width: '100%',
                display: 'flex',
                flexShrink: 0,
              }}>
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
                  margin: '0 16px',
                  borderRadius: '4px',
                }}
                twWrapperStyles={{
                  width: 'calc(100% - 32px)',
                  display: 'block',
                }}>
                Publish Prompt
              </Button>
            </Box>
          </>
        )}
      </Box>
    </ResizableDrawer>
  );
};
