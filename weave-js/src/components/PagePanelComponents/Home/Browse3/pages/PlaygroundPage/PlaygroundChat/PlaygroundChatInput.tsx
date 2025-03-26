import {Box, Divider} from '@mui/material';
import {MOON_250, MOON_500} from '@wandb/weave/common/css/color.styles';
import {Button} from '@wandb/weave/components/Button';
import React, {useState} from 'react';

import {StyledTextArea} from '../../../StyledTextarea';
import {PlaygroundMessageRole} from '../types';

type PlaygroundChatInputProps = {
  chatText: string;
  setChatText: (text: string) => void;
  isLoading: boolean;
  onSend: (role: PlaygroundMessageRole, chatText: string) => void;
  onAdd: (role: PlaygroundMessageRole, chatText: string) => void;
  settingsTab: number | null;
  hasConfiguredProviders?: boolean;
};

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
  chatText,
  setChatText,
  isLoading,
  onSend,
  onAdd,
  settingsTab,
  hasConfiguredProviders = true,
}) => {
  const [addMessageRole, setAddMessageRole] =
    useState<PlaygroundMessageRole>('user');
  const [shouldReset, setShouldReset] = useState(false);

  const handleReset = () => {
    setShouldReset(true);
    setTimeout(() => setShouldReset(false), 0);
  };

  const handleSend = (role: PlaygroundMessageRole) => {
    onSend(role, chatText);
    handleReset();
  };

  const handleAdd = (role: PlaygroundMessageRole, text: string) => {
    onAdd(role, text);
    handleReset();
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      handleSend(addMessageRole);
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
          placeholder={
            hasConfiguredProviders
              ? 'Type your message here...'
              : 'Configure a provider to start chatting...'
          }
          autoGrow
          maxHeight={160}
          reset={shouldReset}
          disabled={!hasConfiguredProviders}
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
              disabled={
                isLoading || chatText.trim() === '' || !hasConfiguredProviders
              }
              onClick={() => handleAdd(addMessageRole, chatText)}>
              Add
            </Button>
            <Divider orientation="vertical" flexItem sx={{bgcolor: MOON_250}} />
            <Button
              size="medium"
              onClick={() => handleSend(addMessageRole)}
              disabled={
                isLoading || chatText.trim() === '' || !hasConfiguredProviders
              }
              startIcon={isLoading ? 'loading' : undefined}>
              {isLoading ? 'Sending...' : 'Send'}
            </Button>
          </Box>
        </Box>
      </Box>
    </Box>
  );
};
