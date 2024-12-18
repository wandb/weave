/**
 * Show code in the Monaco editor.
 */

import {Editor} from '@monaco-editor/react';
import {Box} from '@mui/material';
import React from 'react';

import {sanitizeString} from '../../../../../util/sanitizeSecrets';
import {Loading} from '../../../../Loading';
import {useWFHooks} from '../pages/wfReactInterface/context';

// Simple language detection based on file extension or content
// TODO: Unify this utility method with Browse2OpDefCode.tsx
export const detectLanguage = (uri: string, code: string) => {
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

type CodeViewProps = {
  uri: string;
  maxLines?: number;
};

const DEFAULT_MAX_LINES = 20;

export const CodeView = ({uri, maxLines}: CodeViewProps) => {
  const {
    derived: {useCodeForOpRef},
  } = useWFHooks();
  const opContentsQuery = useCodeForOpRef(uri);
  const text = opContentsQuery.result ?? '';
  const {loading} = opContentsQuery;

  if (loading) {
    return <Loading centered size={25} />;
  }

  const sanitized = sanitizeString(text);
  const language = detectLanguage(uri, sanitized);

  const inner = (
    <Editor
      height="100%"
      language={language}
      loading={loading}
      value={sanitized}
      options={{
        readOnly: true,
        minimap: {enabled: false},
        scrollBeyondLastLine: false,
        scrollbar: {
          handleMouseWheel: true, // Make horizontal scrolling with wheel work
          alwaysConsumeMouseWheel: false, // Don't capture page scroll
        },
        padding: {top: 10, bottom: 10},
      }}
    />
  );

  const totalLines = sanitized.split('\n').length ?? 0;
  const showLines = Math.min(totalLines, maxLines ?? DEFAULT_MAX_LINES);
  const lineHeight = 18;
  const padding = 20;
  const height = showLines * lineHeight + padding + 'px';
  return <Box sx={{height}}>{inner}</Box>;
};
