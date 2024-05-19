/**
 * Wrap Monaco editor. See also:
 * import MonacoEditor from '@wandb/weave/common/components/Monaco/Editor';
 * This is a controlled component that automatically sets its height based on
 * the text content.
 */

import {MOON_250} from '@wandb/weave/common/css/globals.styles';
import React, {useRef, useState} from 'react';

const Editor = React.lazy(async () => {
  await import('@wandb/weave/common/components/Monaco/bootstrap');
  return await import('@monaco-editor/react');
});

const BORDER_PX = 1;

type CodeEditorProps = {
  value: string;
  language?: string;
  readOnly?: boolean;
  onChange?: (value: string) => void;
  maxHeight?: number;
  minHeight?: number;

  // To enable horizontal scrolling with the mouse wheel and not just the scrollbar,
  // set handleMouseWheel to true and alwaysConsumeMouseWheel to false.
  handleMouseWheel?: boolean;
  alwaysConsumeMouseWheel?: boolean;
};

export const CodeEditor = ({
  value,
  language,
  readOnly,
  onChange,
  maxHeight,
  minHeight,
  handleMouseWheel,
  alwaysConsumeMouseWheel,
}: CodeEditorProps) => {
  const editorRef = useRef(null);
  const [height, setHeight] = useState(300);

  const updateHeight = () => {
    const editor: any = editorRef.current;
    if (editor) {
      // box-sizing is border-box, so include border in height.
      const contentHeight = editor.getContentHeight() + 2 * BORDER_PX;
      const realMin = minHeight
        ? Math.max(minHeight, contentHeight)
        : contentHeight;
      setHeight(maxHeight ? Math.min(maxHeight, realMin) : realMin);
    }
  };

  const handleEditorBeforeMount = (monaco: any) => {
    monaco.editor.defineTheme('wandb-light', {
      base: 'vs',
      inherit: true,
      rules: [],
      colors: {
        'editorWidget.border': MOON_250,
      },
    });
  };

  const handleEditorDidMount = (editor: any, monaco: any) => {
    monaco.editor.setTheme('wandb-light');
    editorRef.current = editor;
    editor.onDidContentSizeChange(updateHeight);
    updateHeight();
  };

  const width = '100%';
  const options = {
    readOnly,
    minimap: {
      enabled: false,
    },
    overviewRulerLanes: 0,
    scrollBeyondLastLine: false,
    scrollbar: {
      handleMouseWheel: handleMouseWheel ?? false,
      alwaysConsumeMouseWheel: alwaysConsumeMouseWheel ?? true,
    },
  };

  const onValueChange = (newValue: string | undefined) => {
    if (onChange) {
      onChange(newValue ?? '');
    }
  };

  return (
    <div
      style={{
        width,
        height: `${height}px`,
        border: `${BORDER_PX}px solid ${MOON_250}`,
      }}>
      <React.Suspense fallback={<></>}>
        <Editor
          height="100%"
          value={value}
          language={language}
          beforeMount={handleEditorBeforeMount}
          onMount={handleEditorDidMount}
          onChange={onValueChange}
          options={options}
        />
      </React.Suspense>
    </div>
  );
};
