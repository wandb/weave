import Editor from '@monaco-editor/react';
import React, {FC, useMemo} from 'react';

import {isWeaveObjectRef, parseRef} from '../../../../react';
import {useWFHooks} from '../Browse3/pages/wfReactInterface/context';

export const Browse2OpDefCode: FC<{uri: string}> = ({uri}) => {
  // TODO: This only works with the new objects trace_server

  // const opPyContents = useMemo(() => {
  //   return opDefCodeNode(uri);
  // }, [uri]);
  // const opPyContentsQuery = useNodeValue(opPyContents);
  // const text = opPyContentsQuery.loading ? '' : opPyContentsQuery.result;

  const {useRefsData, useFileContent} = useWFHooks();
  const query = useRefsData([uri]);
  const fileSpec = useMemo(() => {
    if (query.result == null) {
      return null;
    }
    const result = query.result[0];
    const ref = parseRef(uri);
    if (isWeaveObjectRef(ref)) {
      return {
        digest: result.files['obj.py'],
        entity: ref.entityName,
        project: ref.projectName,
      };
    }
    return null;
  }, [query.result, uri]);
  const text = useFileContent(
    fileSpec?.entity ?? '',
    fileSpec?.project ?? '',
    fileSpec?.digest ?? '',
    {skip: fileSpec == null}
  );

  return (
    <Editor
      height={'100%'}
      defaultLanguage="python"
      loading={query.loading}
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
