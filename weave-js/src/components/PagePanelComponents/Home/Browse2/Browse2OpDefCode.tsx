import Editor from '@monaco-editor/react';
import Box from '@mui/material/Box';
import {Loading} from '@wandb/weave/components/Loading';
import React, {FC} from 'react';

import {Alert} from '../../../Alert';
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
    return (
      <Box
        sx={{
          height: '38px',
          width: '100%',
        }}>
        <Loading centered size={25} />
      </Box>
    );
  }

  if (text.result == null) {
    return (
      <Box
        sx={{
          margin: '10px 16px 0 10px',
        }}>
        <Alert severity="warning">No code found for this operation</Alert>
      </Box>
    );
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
    const totalLines = text.result?.split('\n').length ?? 0;
    const showLines = Math.min(totalLines, maxRowsInView);
    const lineHeight = 18;
    const padding = 20;
    const height = showLines * lineHeight + padding + 'px';
    return <Box sx={{height}}>{inner}</Box>;
  }
  return inner;
};
