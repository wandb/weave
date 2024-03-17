import Editor from '@monaco-editor/react';
import React, {FC, useMemo} from 'react';

import {useWFHooks} from '../Browse3/pages/wfReactInterface/context';

export const Browse2OpDefCode: FC<{uri: string}> = ({uri}) => {
  // TODO: This only works with the new objects trace_server

  // const opPyContents = useMemo(() => {
  //   return opDefCodeNode(uri);
  // }, [uri]);
  // const opPyContentsQuery = useNodeValue(opPyContents);
  // const text = opPyContentsQuery.loading ? '' : opPyContentsQuery.result;

  const {useRefsData} = useWFHooks();
  const query = useRefsData([uri]);
  const text = useMemo(() => {
    if (query.result == null) {
      return '';
    }
    const b64obj = query.result[0].files['obj.py'];
    return atob(b64obj);
  }, [query]);
  return (
    <Editor
      height={'100%'}
      defaultLanguage="python"
      loading={query.loading}
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
