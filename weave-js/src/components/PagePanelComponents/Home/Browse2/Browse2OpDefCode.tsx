import Editor from '@monaco-editor/react';
import React, {FC} from 'react';

import {useWFHooks} from '../Browse3/pages/wfReactInterface/context';

export const Browse2OpDefCode: FC<{uri: string}> = ({uri}) => {
  const {
    derived: {useCodeForOpRef},
  } = useWFHooks();
  const text = useCodeForOpRef(uri);

  return (
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
};
