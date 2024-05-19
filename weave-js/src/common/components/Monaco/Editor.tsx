// A wrapper around Monaco editor that maintains its own value
// in state. This prevents update issues (jumping around when the value
// prop coming in changes). Change the key to send a new value in.

import {EditorProps} from '@monaco-editor/react';
import type {editor as editorTypes} from 'monaco-editor';
import React from 'react';
import {useEffect, useState} from 'react';
import {Loader} from 'semantic-ui-react';

const MonacoEditor = React.lazy(async () => {
  await import('./bootstrap');
  return await import('@monaco-editor/react');
});

const EditorLoading = ({height}: {height?: string | number}) => (
  <div style={{height: height || 400}}>
    <Loader>Loading editor</Loader>
  </div>
);

type OnChangeStringOnly = (
  val: string,
  e: editorTypes.IModelContentChangedEvent
) => void;

const Editor = (
  props: Omit<EditorProps, 'onChange' | 'defaultLanguage'> & {
    onChange: OnChangeStringOnly;
    language: EditorProps['defaultLanguage'];
    wordWrap?: boolean;
  }
) => {
  const {
    onChange,
    height,
    onMount,
    options,
    theme,
    language,
    wordWrap,
    ...rest
  } = props;

  const [value, setValue] = useState(props.value || '');
  useEffect(() => {
    setValue(props.value || '');
  }, [props.value]);

  return (
    <div className={props.className ?? ''} style={{minWidth: 400}}>
      <React.Suspense fallback={<EditorLoading height={height} />}>
        <MonacoEditor
          height={height || 600}
          {...rest}
          defaultLanguage={language}
          value={value}
          onChange={(val, e) => {
            setValue(val || '');
            if (onChange) {
              onChange(val || '', e);
            }
          }}
          theme={theme}
          onMount={onMount}
          options={Object.assign(
            {
              autoClosingBrackets: 'never',
              autoClosingQuotes: 'never',
              automaticLayout: true,
              cursorBlinking: 'smooth',
              folding: true,
              lineNumbersMinChars: 4,
              minimap: {enabled: false},
              scrollBeyondLastLine: false,
              wordWrap: wordWrap ?? 'on',
            },
            options || {}
          )}
        />
      </React.Suspense>
    </div>
  );
};

export default Editor;
