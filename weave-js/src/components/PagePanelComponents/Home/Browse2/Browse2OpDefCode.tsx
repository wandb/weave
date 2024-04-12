import {Box} from '@material-ui/core';
import Editor from '@monaco-editor/react';
import {Loading} from '@wandb/weave/components/Loading';
import React, {FC} from 'react';

import {useWFHooks} from '../Browse3/pages/wfReactInterface/context';

export const Browse2OpDefCode: FC<{uri: string; maxRowsInView?: number}> = ({
  uri,
  maxRowsInView,
}) => {
  const {
    derived: {useCodeForOpRef},
  } = useWFHooks();
  const text = useCodeForOpRef(uri);
  if (text.loading) {
    return <Loading centered />;
  }

  const inner = (
    <Editor
      height={'100%'}
      defaultLanguage="python"
      loading={text.loading}
      value={text.result ?? ''}
      options={{
        readOnly: true,
        minimap: {enabled: false},
        scrollBeyondLastLine: false,
        padding: {top: 10, bottom: 10},
      }}
    />
  );
  if (maxRowsInView) {
    let height = '100%';
    const totalLines = text.result?.split('\n').length ?? 0;
    const lineHeight = 18;
    const padding = 20;
    const maxHeight = maxRowsInView * lineHeight + padding;
    const targetHeight = totalLines * lineHeight + padding;
    if (targetHeight > maxHeight) {
      height = `${maxHeight}px`;
    } else {
      height = `${targetHeight}px`;
    }
    return <Box sx={{height}}>{inner}</Box>;
  }
  return inner;
};
