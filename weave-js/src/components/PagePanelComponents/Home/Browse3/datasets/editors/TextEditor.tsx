import {TextField} from '@mui/material';
import React from 'react';

interface TextEditorProps {
  value: string;
  onChange: (value: string) => void;
  onClose: () => void;
  inputRef?: React.RefObject<HTMLTextAreaElement>;
}

export const TextEditor: React.FC<TextEditorProps> = ({
  value,
  onChange,
  onClose,
  inputRef,
}) => {
  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.metaKey) {
      event.stopPropagation();
    } else if (event.key === 'Enter' && event.metaKey) {
      onClose();
    }
  };

  return (
    <TextField
      inputRef={inputRef}
      value={value}
      onChange={e => onChange(e.target.value)}
      onKeyDown={handleKeyDown}
      onFocus={e => {
        const target = e.target as HTMLTextAreaElement;
        target.setSelectionRange(target.value.length, target.value.length);
      }}
      fullWidth
      multiline
      autoFocus
      sx={{
        width: '100%',
        '& .MuiInputBase-root': {
          fontFamily: '"Source Sans Pro", sans-serif',
          fontSize: '14px',
          border: 'none',
          backgroundColor: 'white',
        },
        '& .MuiInputBase-input': {
          padding: '0px',
        },
        '& .MuiOutlinedInput-notchedOutline': {
          border: 'none',
        },
        '& textarea': {
          overflow: 'hidden !important',
          resize: 'none',
        },
      }}
    />
  );
};
