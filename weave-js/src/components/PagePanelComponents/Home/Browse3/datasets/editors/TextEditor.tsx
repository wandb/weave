import {TextField} from '@mui/material';
import React from 'react';

interface TextEditorProps {
  value: string;
  onChange: (value: string) => void;
  onClose: (value?: any) => void;
  inputRef?: React.RefObject<HTMLTextAreaElement>;
}

export const TextEditor: React.FC<TextEditorProps> = ({
  value,
  onChange,
  onClose,
  inputRef,
}) => {
  const localInputRef = React.useRef<HTMLTextAreaElement | null>(null);
  const actualInputRef = inputRef || localInputRef;

  const handleKeyDown = (event: React.KeyboardEvent) => {
    // Only prevent propagation for normal Enter key
    if (event.key === 'Enter' && !event.metaKey) {
      event.stopPropagation();
    } else if (event.key === 'Enter' && event.metaKey) {
      event.stopPropagation();
      // Get the current value directly when closing
      onClose(value);
    } else if (event.key === 'Escape') {
      event.stopPropagation();
      // Also get the value directly when escaping
      onClose(value);
    }
  };

  return (
    <TextField
      inputRef={actualInputRef}
      value={value}
      onChange={e => {
        const newValue = e.target.value;
        onChange(newValue);
      }}
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
