import {DiffEditor, Monaco} from '@monaco-editor/react';
import {useNodeValue} from '@wandb/weave/react';
import React, {useMemo} from 'react';

import {opDefCodeNode} from '../Browse2/dataModel';

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
  const opPyContentsLeft = useMemo(() => {
    return opDefCodeNode(left);
  }, [left]);
  const opPyContentsRight = useMemo(() => {
    return opDefCodeNode(right);
  }, [right]);
  const opPyContentsQueryLeft = useNodeValue(opPyContentsLeft);
  const opPyContentsQueryRight = useNodeValue(opPyContentsRight);
  const textLeft = opPyContentsQueryLeft.loading
    ? ''
    : opPyContentsQueryLeft.result;
  const textRight = opPyContentsQueryRight.loading
    ? ''
    : opPyContentsQueryRight.result;
  const loading =
    opPyContentsQueryLeft.loading || opPyContentsQueryRight.loading;

  const onMount = (editor: any, monaco: Monaco) => {
    if (onSplitResize) {
      editor.getOriginalEditor().onDidLayoutChange((dimensions: any) => {
        onSplitResize(dimensions.width);
      });
    }
  };

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
