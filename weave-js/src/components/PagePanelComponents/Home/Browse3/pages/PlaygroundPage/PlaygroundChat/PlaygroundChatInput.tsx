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
};

export const PlaygroundChatInput: React.FC<PlaygroundChatInputProps> = ({
  chatText,
  setChatText,
  isLoading,
  onSend,
  onAdd,
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
        width: 'calc(100% - 32px)',
        maxHeight: '500px',
        minWidth: '500px',
        maxWidth: '800px',
        border: `2px solid ${TEAL_500}`,
        padding: '8px',
        paddingLeft: '12px',
        marginX: '16px',
        marginBottom: '16px',
        borderRadius: '4px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        gap: '8px',
        position: 'relative',
      }}>
      <Box
        sx={{
          position: 'absolute',
          top: '-30px',
          right: '0',
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
              color: MOON_500,
              fontSize: '12px',
            }}>
            Add as
            <Button
              className="ml-4"
              variant="secondary"
              size="small"
              active={addMessageRole === 'assistant'}
              onClick={() => setAddMessageRole('assistant')}>
              Assistant
            </Button>
            <Button
              variant="secondary"
              size="small"
              active={addMessageRole === 'user'}
              onClick={() => setAddMessageRole('user')}>
              User
            </Button>
          </Box>
          <Button
            variant="secondary"
            size="small"
            startIcon="add-new"
            onClick={() => onAdd(addMessageRole, chatText)}>
            Add
          </Button>
          <Divider orientation="vertical" flexItem sx={{bgcolor: MOON_250}} />
          <Button
            size="small"
            onClick={() => onSend(addMessageRole)}
            disabled={isLoading || chatText.trim() === ''}
            startIcon={isLoading ? 'loading' : undefined}>
            {isLoading ? 'Sending...' : 'Send'}
          </Button>
        </Box>
      </Box>
    </Box>
  );
};
