import {TextField} from '@mui/material';
import React, {useRef} from 'react';

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
  const localInputRef = useRef<HTMLTextAreaElement | null>(null);
  const actualInputRef = inputRef || localInputRef;

  const handleKeyDown = (event: React.KeyboardEvent) => {
    // Only prevent propagation for normal Enter key
    if (event.key === 'Enter' && !event.metaKey) {
      event.stopPropagation();
    } else if (event.key === 'Enter' && event.metaKey) {
      event.preventDefault();
      event.stopPropagation();
      // Get the current value directly when closing
      onClose(value);
    } else if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      // Escape should cancel without applying changes
      onClose();
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
      // Focus the input and position cursor at the end
      onFocus={e => {
        const target = e.target as HTMLTextAreaElement;
        target.setSelectionRange(target.value.length, target.value.length);
      }}
      fullWidth
      multiline
      autoFocus
      sx={{
        width: '100%',
        height: '100%',
        '& .MuiInputBase-root': {
          fontFamily: '"Source Sans Pro", sans-serif',
          fontSize: '14px',
          border: 'none',
          backgroundColor: 'white',
          height: '100%',
        },
        '& .MuiInputBase-input': {
          padding: '0px',
          height: '100%',
        },
        '& .MuiOutlinedInput-notchedOutline': {
          border: 'none',
        },
        '& textarea': {
          overflow: 'auto !important',
          height: '100% !important',
          resize: 'none',
        },
      }}
    />
  );
};
