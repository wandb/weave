import {DiffEditor as MonacoDiffEditor} from '@monaco-editor/react';
import {Box} from '@mui/material';
import type {editor as monacoEditor} from 'monaco-editor';
import React from 'react';

interface DiffEditorProps {
  value: string;
  originalValue: string;
  onChange: (value: string) => void;
  onClose: () => void;
}

export const DiffEditor: React.FC<DiffEditorProps> = ({
  value,
  originalValue,
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
      <MonacoDiffEditor
        height="100%"
        original={originalValue}
        modified={value}
        onMount={(editor: monacoEditor.IStandaloneDiffEditor, monaco) => {
          const modifiedEditor = editor.getModifiedEditor();
          modifiedEditor.addAction({
            id: 'closeEditor',
            label: 'Close Editor',
            keybindings: [monaco.KeyMod.CtrlCmd + monaco.KeyCode.Enter],
            run: () => {
              onClose();
            },
          });

          const keyDisposable = modifiedEditor.onKeyDown(e => {
            if (e.browserEvent.key === 'Enter' && !e.browserEvent.metaKey) {
              e.browserEvent.preventDefault();
              e.browserEvent.stopPropagation();
              modifiedEditor.trigger('keyboard', 'type', {text: '\n'});
            }
          });

          const changeDisposable = modifiedEditor.onDidChangeModelContent(
            () => {
              const model = modifiedEditor.getModel();
              if (model) {
                onChange(model.getValue());
              }
            }
          );

          modifiedEditor.onDidDispose(() => {
            keyDisposable.dispose();
            changeDisposable.dispose();
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
