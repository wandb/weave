import {DiffEditor, Monaco} from '@monaco-editor/react';
import React from 'react';

import {Loading} from '../../../Loading';
import {useWFHooks} from './pages/wfReactInterface/context';

type OpCodeViewerDiffProps = {
  left: string;
  right: string;

  onSplitResize?: (left: number) => void;
};

export const OpCodeViewerDiff = ({
  left,
  right,
  onSplitResize,
}: OpCodeViewerDiffProps) => {
  const {
    derived: {useCodeForOpRef},
  } = useWFHooks();
  const opPyContentsQueryLeft = useCodeForOpRef(left);
  const opPyContentsQueryRight = useCodeForOpRef(right);
  const textLeft = opPyContentsQueryLeft.result ?? '';
  const textRight = opPyContentsQueryRight.result ?? '';
  const loading =
    opPyContentsQueryLeft.loading || opPyContentsQueryRight.loading;

  const onMount = (editor: any, monaco: Monaco) => {
    if (onSplitResize) {
      editor.getOriginalEditor().onDidLayoutChange((dimensions: any) => {
        if (dimensions.contentWidth >= 0) {
          onSplitResize(dimensions.width);
        }
      });
    }
  };

  if (loading) {
    return <Loading centered size={25} />;
  }

  return (
    <DiffEditor
      height="100%"
      originalLanguage="python"
      modifiedLanguage="python"
      loading={loading}
      original={textLeft}
      modified={textRight}
      onMount={onMount}
      options={{
        readOnly: true,
        minimap: {enabled: false},
        scrollBeyondLastLine: false,
        padding: {top: 10, bottom: 10},
      }}
    />
  );
};
