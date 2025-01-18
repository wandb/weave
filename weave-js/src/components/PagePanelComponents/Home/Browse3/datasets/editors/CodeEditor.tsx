import {Editor} from '@monaco-editor/react';
import {Box} from '@mui/material';
import React from 'react';

interface CodeEditorProps {
  value: string;
  onChange: (value: string) => void;
  onClose: () => void;
}

export const CodeEditor: React.FC<CodeEditorProps> = ({
  value,
  onChange,
  onClose,
}) => {
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
        onChange={newValue => onChange(newValue ?? '')}
        onMount={(editor, monacoInstance) => {
          editor.addAction({
            id: 'closeEditor',
            label: 'Close Editor',
            keybindings: [
              monacoInstance.KeyMod.CtrlCmd + monacoInstance.KeyCode.Enter,
            ],
            run: () => {
              onClose();
            },
          });
          const disposable = editor.onKeyDown(e => {
            if (e.browserEvent.key === 'Enter' && !e.browserEvent.metaKey) {
              e.browserEvent.preventDefault();
              e.browserEvent.stopPropagation();
              editor.trigger('keyboard', 'type', {text: '\n'});
            }
          });

          editor.onDidDispose(() => {
            disposable.dispose();
          });
        }}
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
