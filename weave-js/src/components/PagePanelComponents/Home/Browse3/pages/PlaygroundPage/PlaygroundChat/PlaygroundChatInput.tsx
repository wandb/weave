import {Box, Divider} from '@mui/material';
import {MOON_250, MOON_500} from '@wandb/weave/common/css/color.styles';
import {Button} from '@wandb/weave/components/Button';
import React, {useState} from 'react';

import {StyledTextArea} from '../../../StyledTextarea';
import {PlaygroundMessageRole} from '../types';
import {PlaygroundState} from '../types';
import {SetPlaygroundStateFieldFunctionType} from './useChatFunctions';

interface PlaygroundChatInputProps {
  playgroundState: PlaygroundState;
  setPlaygroundStateField: SetPlaygroundStateFieldFunctionType;
  idx: number;
  entity: string;
  project: string;
  chatText: string;
  setChatText: (text: string) => void;
  isLoading: boolean;
  handleSend: (
    role: PlaygroundMessageRole,
    chatText: string,
    callIndex?: number,
    content?: string,
    toolCallId?: string
  ) => Promise<void>;
  handleAddMessage: (role: PlaygroundMessageRole, text: string) => void;
  settingsTab: number | null;
}

const isMac = () => {
  const platform = navigator.platform || '';
  const userAgent = navigator.userAgent || '';
  const appVersion = navigator.appVersion || '';
  const checkString = (str: string) => /Mac|iPhone|iPod|iPad/i.test(str);
  return (
    checkString(platform) || checkString(userAgent) || checkString(appVersion)
  );
};

export const PlaygroundChatInput: React.FC<PlaygroundChatInputProps> = ({
  playgroundState,
  setPlaygroundStateField,
  idx,
  entity,
  project,
  chatText,
  setChatText,
  isLoading,
  handleSend,
  handleAddMessage,
  settingsTab,
}) => {
  const [addMessageRole, setAddMessageRole] =
    useState<PlaygroundMessageRole>('user');
  const [shouldReset, setShouldReset] = useState(false);

  const handleReset = () => {
    setShouldReset(true);
    setTimeout(() => setShouldReset(false), 0);
  };

  const handleSendMessage = async (role: PlaygroundMessageRole) => {
    await handleSend(role, chatText);
    handleReset();
  };

  const handleAddMessageRole = (role: PlaygroundMessageRole, text: string) => {
    handleAddMessage(role, text);
    handleReset();
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      handleSendMessage(addMessageRole);
    }
  };

  return (
    <Box
      sx={{
        position: 'fixed',
        bottom: '0',
        left: '58px',
        paddingBottom: '16px',
        paddingTop: '8px',
        backgroundColor: 'white',
        width:
          settingsTab !== null
            ? 'calc(100% - 58px - 320px)'
            : 'calc(100% - 58px)',
        zIndex: 1, // WARN: z-index position of navbar overflow menu is `2`, check first if changing
      }}>
      <Box
        sx={{
          maxWidth: '800px',
          marginX: 'auto',
        }}>
        <Box
          sx={{
            marginBottom: '4px',
            textAlign: 'right',
            fontSize: '12px',
            color: MOON_500,
          }}>
          Press {isMac() ? 'CMD' : 'Ctrl'} + Enter to send
        </Box>
        <StyledTextArea
          onChange={e => setChatText(e.target.value)}
          value={chatText}
          onKeyDown={handleKeyDown}
          placeholder="Type your message here..."
          autoGrow
          maxHeight={160}
          reset={shouldReset}
        />
        <Box sx={{display: 'flex', justifyContent: 'space-between'}}>
          <Box sx={{display: 'flex', gap: '8px'}}>
            {/* TODO: Add image upload */}
            {/* <Button variant="secondary" size="small" startIcon="photo" /> */}
          </Box>
          <Box sx={{display: 'flex', gap: '8px'}}>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                color: MOON_500,
                fontSize: '12px',
              }}>
              Add as
              <Button
                className="ml-4 rounded-r-none"
                variant="secondary"
                size="medium"
                active={addMessageRole === 'system'}
                onClick={() => setAddMessageRole('system')}>
                System
              </Button>
              <Button
                className="rounded-none"
                variant="secondary"
                size="medium"
                active={addMessageRole === 'assistant'}
                onClick={() => setAddMessageRole('assistant')}>
                Assistant
              </Button>
              <Button
                className="rounded-l-none"
                variant="secondary"
                size="medium"
                active={addMessageRole === 'user'}
                onClick={() => setAddMessageRole('user')}>
                User
              </Button>
            </Box>
            <Button
              variant="secondary"
              size="medium"
              startIcon="add-new"
              onClick={() => handleAddMessageRole(addMessageRole, chatText)}>
              Add
            </Button>
            <Divider orientation="vertical" flexItem sx={{bgcolor: MOON_250}} />
            <Button
              size="medium"
              onClick={() => handleSendMessage(addMessageRole)}
              disabled={isLoading || chatText.trim() === ''}
              startIcon={isLoading ? 'loading' : undefined}>
              {isLoading ? 'Sending...' : 'Send'}
            </Button>
          </Box>
        </Box>
      </Box>
    </Box>
  );
};
