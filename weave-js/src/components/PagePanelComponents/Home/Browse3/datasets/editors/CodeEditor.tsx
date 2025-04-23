import {Editor} from '@monaco-editor/react';
import {Box} from '@mui/material';
import React, {useRef} from 'react';

interface CodeEditorProps {
  value: string;
  onChange: (value: string) => void;
  onClose: (value?: any) => void;
  language?: string;
  disableClosing?: boolean;
}

export const CodeEditor: React.FC<CodeEditorProps> = ({
  value,
  onChange,
  onClose,
  language,
  disableClosing = false,
}) => {
  const editorRef = useRef<any>(null);
  const currentValueRef = useRef(value);

  const handleEditorDidMount = (editor: any, monaco: any) => {
    editorRef.current = editor;

    // Set initial value
    if (editor.getValue() !== value) {
      editor.setValue(value);
    }

    // Track content changes
    editor.onDidChangeModelContent(() => {
      const newValue = editor.getValue();
      currentValueRef.current = newValue;
      onChange(newValue);
    });

    // Override the default Enter key behavior to prevent newlines on Cmd+Enter
    editor.onKeyDown((e: any) => {
      if ((e.metaKey || e.ctrlKey) && e.code === 'Enter') {
        e.preventDefault();
        e.stopPropagation();

        // Don't close if closing is disabled
        if (disableClosing) {
          return;
        }

        // Get the latest value directly from the editor
        onClose(editor.getValue());
      } else if (e.code === 'Escape') {
        e.preventDefault();
        e.stopPropagation();

        // Don't close if closing is disabled
        if (disableClosing) {
          return;
        }

        // Escape cancels the edit
        onClose();
      }
    });
  };

  // Update ref when value changes
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
      <Editor
        height="100%"
        width="100%"
        value={value}
        language={language}
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
