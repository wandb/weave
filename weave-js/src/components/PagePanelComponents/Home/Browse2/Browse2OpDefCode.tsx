import Editor from '@monaco-editor/react';
import {useNodeValue} from '@wandb/weave/react';
import React, {FC, useMemo} from 'react';

import {opDefCodeNode} from './dataModel';

export const Browse2OpDefCode: FC<{uri: string}> = ({uri}) => {
  const opPyContents = useMemo(() => {
    return opDefCodeNode(uri);
  }, [uri]);
  const opPyContentsQuery = useNodeValue(opPyContents);
  const text = opPyContentsQuery.result ?? '';
  return (
    <Editor
      height={'100%'}
      defaultLanguage="python"
      loading={opPyContentsQuery.loading}
      value={text}
      options={{
        readOnly: true,
        minimap: {enabled: false},
        scrollBeyondLastLine: false,
        padding: {top: 10, bottom: 10},
      }}
    />
  );
};
