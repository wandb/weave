/**
 * Show code in the Monaco editor. If code has changed show a diff.
 */

import {DiffEditor, Editor} from '@monaco-editor/react';
import {Box} from '@mui/material';
import React from 'react';

import {sanitizeString} from '../../../../../util/sanitizeSecrets';
import {Loading} from '../../../../Loading';
import {useWFHooks} from '../pages/wfReactInterface/context';

// Simple language detection based on file extension or content
// TODO: Unify this utility method with Browse2OpDefCode.tsx
const detectLanguage = (uri: string, code: string) => {
  if (uri.endsWith('.py')) {
    return 'python';
  }
  if (uri.endsWith('.js') || uri.endsWith('.ts')) {
    return 'javascript';
  }
  if (code.includes('def ') || code.includes('import ')) {
    return 'python';
  }
  if (code.includes('function ') || code.includes('const ')) {
    return 'javascript';
  }
  return 'plaintext';
};

type CodeDiffProps = {
  oldValueRef: string;
  newValueRef: string;
};

export const CodeDiff = ({oldValueRef, newValueRef}: CodeDiffProps) => {
  const {
    derived: {useCodeForOpRef},
  } = useWFHooks();
  const opContentsQueryOld = useCodeForOpRef(oldValueRef);
  const opContentsQueryNew = useCodeForOpRef(newValueRef);
  const textOld = opContentsQueryOld.result ?? '';
  const textNew = opContentsQueryNew.result ?? '';
  const loading = opContentsQueryOld.loading || opContentsQueryNew.loading;

  if (loading) {
    return <Loading centered size={25} />;
  }

  const sanitizedOld = sanitizeString(textOld);
  const sanitizedNew = sanitizeString(textNew);
  const languageOld = detectLanguage(oldValueRef, sanitizedOld);
  const languageNew = detectLanguage(newValueRef, sanitizedNew);

  const inner =
    sanitizedOld !== sanitizedNew ? (
      <DiffEditor
        height="100%"
        originalLanguage={languageOld}
        modifiedLanguage={languageNew}
        loading={loading}
        original={sanitizedOld}
        modified={sanitizedNew}
        options={{
          readOnly: true,
          minimap: {enabled: false},
          scrollBeyondLastLine: false,
          padding: {top: 10, bottom: 10},
          renderSideBySide: false,
        }}
      />
    ) : (
      <Editor
        height="100%"
        language={languageNew}
        loading={loading}
        value={sanitizedNew}
        options={{
          readOnly: true,
          minimap: {enabled: false},
          scrollBeyondLastLine: false,
          padding: {top: 10, bottom: 10},
        }}
      />
    );

  const maxRowsInView = 20;
  const totalLines = sanitizedNew.split('\n').length ?? 0;
  const showLines = Math.min(totalLines, maxRowsInView);
  const lineHeight = 18;
  const padding = 20;
  const height = showLines * lineHeight + padding + 'px';
  return <Box sx={{height}}>{inner}</Box>;
};
