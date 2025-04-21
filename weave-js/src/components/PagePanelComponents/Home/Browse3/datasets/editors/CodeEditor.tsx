import {Editor} from '@monaco-editor/react';
import {Box} from '@mui/material';
import React, {useRef} from 'react';

interface CodeEditorProps {
  value: string;
  onChange: (value: string) => void;
  onClose: (value?: any) => void;
  language?: string;
}

export const CodeEditor: React.FC<CodeEditorProps> = ({
  value,
  onChange,
  onClose,
  language,
}) => {
  const editorRef = useRef<any>(null);
  const currentValueRef = useRef(value);

  const handleEditorDidMount = (editor: any, monaco: any) => {
    editorRef.current = editor;

    // Set initial value
    editor.setValue(value);

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

        // Get the latest value directly from the editor
        onClose(editor.getValue());
      } else if (e.code === 'Escape') {
        e.preventDefault();
        e.stopPropagation();

        // Also close and get value directly from editor
        onClose(editor.getValue());
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
      <Editor
        height="100%"
        width="100%"
        defaultValue={value}
        language={language}
        onChange={newValue => onChange(newValue ?? '')}
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
