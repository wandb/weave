import {DiffEditor as MonacoDiffEditor} from '@monaco-editor/react';
import {Box} from '@mui/material';
import React, {useRef} from 'react';

interface DiffEditorProps {
  value: string;
  originalValue: string;
  onChange: (value: string) => void;
  onClose: (value?: any) => void;
}

export const DiffEditor: React.FC<DiffEditorProps> = ({
  value,
  originalValue,
  onChange,
  onClose,
}) => {
  const editorRef = useRef<any>(null);
  const currentValueRef = useRef(value);

  const handleEditorDidMount = (editor: any, monaco: any) => {
    editorRef.current = editor;

    // Get the modified editor (right side of diff)
    const modifiedEditor = editor.getModifiedEditor();

    // Track content changes
    modifiedEditor.onDidChangeModelContent(() => {
      const newValue = modifiedEditor.getValue();
      currentValueRef.current = newValue;
      onChange(newValue);
    });

    // Override the default Enter key behavior to prevent newlines on Cmd+Enter
    modifiedEditor.onKeyDown((e: any) => {
      if ((e.metaKey || e.ctrlKey) && e.code === 'Enter') {
        e.preventDefault();
        e.stopPropagation();

        // Get the latest value before closing
        onClose(modifiedEditor.getValue());
      } else if (e.code === 'Escape') {
        e.preventDefault();
        e.stopPropagation();

        // Also close and pass value on Escape
        onClose(modifiedEditor.getValue());
      }
    });
  };

  // Update ref when value changes - not using effect now
  currentValueRef.current = value;

  return (
    <Box
      sx={
        {
          height: '100%',
          width: '100%',
          '& .monaco-editor': {
            border: 'none !important',
            outline: 'none !important',
          },
          '& .monaco-editor .overflow-guard': {
            width: '100% !important',
            height: '100% !important',
          },
          '& .monaco-scrollable-element': {
            width: '100% !important',
            height: '100% !important',
          },
        } as const
      }>
      <MonacoDiffEditor
        height="100%"
        original={originalValue}
        modified={value}
        onMount={handleEditorDidMount}
        options={{
          minimap: {enabled: false},
          scrollBeyondLastLine: true,
          fontSize: 12,
          fontFamily: 'monospace',
          lineNumbers: 'on',
          folding: false,
          automaticLayout: true,
          padding: {top: 12, bottom: 12},
          fixedOverflowWidgets: true,
          wordWrap: 'off',
          scrollbar: {
            horizontal: 'auto',
            useShadows: false,
            verticalScrollbarSize: 10,
            horizontalScrollbarSize: 10,
          },
        }}
      />
    </Box>
  );
};
