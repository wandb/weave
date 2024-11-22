import {Box, Divider} from '@mui/material';
import {
  MOON_250,
  MOON_500,
  TEAL_500,
} from '@wandb/weave/common/css/color.styles';
import {Button} from '@wandb/weave/components/Button';
import React, {useState} from 'react';

import {StyledTextArea} from '../StyledTextarea';

type PlaygroundChatInputProps = {
  chatText: string;
  setChatText: (text: string) => void;
  isLoading: boolean;
  onSend: (role: 'assistant' | 'user') => void;
  onAdd: (role: 'assistant' | 'user', text: string) => void;
  settingsTab: number | null;
};

export const PlaygroundChatInput: React.FC<PlaygroundChatInputProps> = ({
  chatText,
  setChatText,
  isLoading,
  onSend,
  onAdd,
  settingsTab,
}) => {
  const [addMessageRole, setAddMessageRole] = useState<'assistant' | 'user'>(
    'user'
  );

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault(); // Prevent default to avoid newline in textarea
      onSend(addMessageRole);
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
        width: settingsTab !== null ? 'calc(100% - 58px - 320px)' : 'calc(100% - 58px)',
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
          Press CMD + Enter to send
        </Box>
        <StyledTextArea
          onChange={e => setChatText(e.target.value)}
          value={chatText}
          onKeyDown={handleKeyDown}
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
            onClick={() => onAdd(addMessageRole, chatText)}>
            Add
          </Button>
          <Divider orientation="vertical" flexItem sx={{bgcolor: MOON_250}} />
          <Button
            size="medium"
            onClick={() => onSend(addMessageRole)}
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
